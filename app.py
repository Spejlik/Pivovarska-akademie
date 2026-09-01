import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import time
import requests
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# =============================================================================
# KONFIGURACE STRÁNKY
# =============================================================================
st.set_page_config(
    page_title="Pivovarská akademie | Kurz sládka",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# INICIALIZACE FIREBASE
# =============================================================================
FIREBASE_WEB_API_KEY = st.secrets.get("FIREBASE_WEB_API_KEY", "")

@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        cred_path = "firebase_credentials.json"
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            st.error("Chybí soubor 'firebase_credentials.json'! Stáhni ho z Firebase Console.")
    return firestore.client()

db = init_firestore()

# =============================================================================
# VÝCHOZÍ MODEL A FIREBASE FUNKCE
# =============================================================================
DEFAULT_STATE = {
    "lessons": {
        "lekce1": {"title": "1. Základy & Suroviny", "completed": False, "score": 0},
        "lekce2": {"title": "2. Voda a její úprava", "completed": False, "score": 0},
        "lekce3": {"title": "3. Rmutování & Enzymy", "completed": False, "score": 0},
        "lekce4": {"title": "4. Scezování & Recirkulace", "completed": False, "score": 0},
        "lekce5": {"title": "5. Kvašení & Diacetyl", "completed": False, "score": 0},
        "lekce6": {"title": "6. Ležákování & KEG CO₂", "completed": False, "score": 0},
        "lekce7": {"title": "7. Senzorika & Pivní vady", "completed": False, "score": 0},
        "lekce8": {"title": "8. Receptury & Tvorba", "completed": False, "score": 0},
        "lekce9_10": {"title": "9 & 10. Checklist & Várka", "completed": False, "score": 0},
    },
    "batch_logs": [],
    "recipes": []
}

def fb_sign_in(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
    res = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    return res.json()

def fb_sign_up(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_WEB_API_KEY}"
    res = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True})
    return res.json()

def load_user_data_from_fb(uid):
    try:
        doc_ref = db.collection("users").document(uid)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return {
                "lessons": data.get("lessons", DEFAULT_STATE["lessons"]),
                "batch_logs": data.get("batch_logs", []),
                "recipes": data.get("recipes", [])
            }
        else:
            doc_ref.set(DEFAULT_STATE)
            return DEFAULT_STATE
    except Exception as e:
        st.error(f"Chyba při stahování dat: {e}")
        return DEFAULT_STATE

def save_data(data):
    if "user_id" in st.session_state and st.session_state.user_id:
        try:
            doc_ref = db.collection("users").document(st.session_state.user_id)
            doc_ref.set({
                "lessons": data.get("lessons", {}),
                "batch_logs": data.get("batch_logs", []),
                "recipes": data.get("recipes", [])
            })
        except Exception as e:
            st.sidebar.error(f"Chyba při ukládání na Firebase: {e}")

# =============================================================================
# SESSION STATE & ČASOVAČ
# =============================================================================
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "kurz" not in st.session_state:
    st.session_state.kurz = DEFAULT_STATE
if "mentor_mode" not in st.session_state:
    st.session_state.mentor_mode = True

if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_recipe_idx" not in st.session_state:
    st.session_state.edit_recipe_idx = None

if "timer_running" not in st.session_state:
    st.session_state.timer_running = False
if "timer_start_time" not in st.session_state:
    st.session_state.timer_start_time = 0.0
if "timer_elapsed_offset" not in st.session_state:
    st.session_state.timer_elapsed_offset = 0.0
if "last_alert_phase" not in st.session_state:
    st.session_state.last_alert_phase = -1

# =============================================================================
# POMOCNÉ FUNKCE
# =============================================================================
def play_sound_alert():
    audio_js = """
    <script>
    try {
        var context = new (window.AudioContext || window.webkitAudioContext)();
        var osc = context.createOscillator();
        var gain = context.createGain();
        osc.type = 'sine';
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.3, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.8);
        osc.connect(gain);
        gain.connect(context.destination);
        osc.start();
        osc.stop(context.currentTime + 0.8);
    } catch(e) {}
    </script>
    """
    st.components.v1.html(audio_js, height=0, width=0)

def render_mentor(tip_text, warning_text=None, action_prompt=None):
    if st.session_state.get("mentor_mode", True):
        st.markdown("---")
        with st.container():
            st.markdown("#### 👨‍🏫 Sládkův mentorský koutek")
            st.info(f"💡 **Tip z praxe:** {tip_text}")
            if warning_text:
                st.warning(f"⚠️ **Pozor na častou chybu:** {warning_text}")
            if action_prompt:
                st.markdown(f"👉 *{action_prompt}*")

# =============================================================================
# SIDEBAR: PŘIHLAŠOVÁNÍ & NAVIGACE
# =============================================================================
st.sidebar.title("🍺 Pivovarská akademie")

if st.session_state.user_id is None:
    st.sidebar.markdown("### 👤 Přihlášení k účtu")
    tab_log, tab_reg = st.sidebar.tabs(["Přihlásit se", "Registrace"])
    
    with tab_log:
        with st.form("form_auth_login"):
            l_email = st.text_input("E-mail")
            l_pass = st.text_input("Heslo", type="password")
            if st.form_submit_button("Přihlásit"):
                res = fb_sign_in(l_email, l_pass)
                if "localId" in res:
                    st.session_state.user_id = res["localId"]
                    st.session_state.user_email = res["email"]
                    st.session_state.kurz = load_user_data_from_fb(res["localId"])
                    st.success("Úspěšně přihlášen!")
                    st.rerun()
                else:
                    st.error("Chyba: Neplatný e-mail nebo heslo.")

    with tab_reg:
        with st.form("form_auth_reg"):
            r_email = st.text_input("E-mail")
            r_pass = st.text_input("Heslo (min. 6 znaků)", type="password")
            if st.form_submit_button("Vytvořit účet"):
                res = fb_sign_up(r_email, r_pass)
                if "localId" in res:
                    st.session_state.user_id = res["localId"]
                    st.session_state.user_email = res["email"]
                    st.session_state.kurz = load_user_data_from_fb(res["localId"])
                    st.success("Účet vytvořen a přihlášen!")
                    st.rerun()
                else:
                    msg = res.get("error", {}).get("message", "Chyba registrace.")
                    st.error(f"Chyba: {msg}")

    st.info("👈 Pro ukládání receptů a postupu v kurzu se přihlas nebo zaregistruj v levém menu.")
    st.divider()

else:
    st.sidebar.success(f"👤 Přihlášen: **{st.session_state.user_email}**")
    if st.sidebar.button("Odhlásit se"):
        st.session_state.user_id = None
        st.session_state.user_email = None
        st.session_state.kurz = DEFAULT_STATE
        st.rerun()
    st.sidebar.divider()

st.session_state.mentor_mode = st.sidebar.toggle("👨‍🏫 Mentorský režim", value=st.session_state.mentor_mode)

completed_count = sum(1 for l in st.session_state.kurz["lessons"].values() if l.get("completed", False))
total_count = len(st.session_state.kurz["lessons"])
progress_val = completed_count / total_count

st.sidebar.markdown(f"**Dokončeno:** `{completed_count} / {total_count} lekcí` ({int(progress_val * 100)} %)")
st.sidebar.progress(progress_val)
st.sidebar.divider()

# 1. Výběr stylu v sidebaru
st.sidebar.subheader("🍺 Nastavení pivního stylu")
zvoleny_styl = st.sidebar.selectbox(
    "Styl pro celý kurz:",
    [
        "Český světlý ležák (Pilsner)",
        "American IPA / APA",
        "Tmavý ležák / Stout",
        "Německé pšeničné (Weizen)"
    ]
)

st.sidebar.divider()

# 2. Zkrácený název pro položku v menu
styl_kratky = "ležáku" if "Pilsner" in zvoleny_styl else ("IPA" if "IPA" in zvoleny_styl else ("pšenice" if "Weizen" in zvoleny_styl else "stoutu"))

# 3. Dynamický seznam menu_items
menu_items = [
    "📘 1. Základy & Suroviny",
    "🚰 2. Voda a její úprava",
    "🔥 3. Rmutování & Enzymy",
    "🪣 4. Scezování & Recirkulace",
    "🧪 5. Kvašení & Diacetyl",
    "❄️ 6. Ležákování & KEG CO₂",
    "👃 7. Senzorika & Pivní vady",
    f"🌾 8. Receptury & Tvorba ({styl_kratky})",
    "📋 9 & 10. Checklist & Várka",
    "📚 Databáze receptů",
    "🧮 Sládkova pokročilá kalkulačka",
    "⏱️ Časovač varného dne"
]
selected_view = st.sidebar.radio("Přejít na:", menu_items)

# =============================================================================
# LEKCE 1: ZÁKLADY & SUROVINY
# =============================================================================
if "1. Základy & Suroviny" in selected_view:
    st.header("📘 Lekce 1: Základy a suroviny")
    st.info(f"🎯 Zvolený pivní styl: **{zvoleny_styl}**")
    
    suroviny_data = {
        "Český světlý ležák (Pilsner)": {
            "slad": "**Plzeňský slad (95–100 %)**. Šetrně sušený ječmenný slad s vysokou enzymatickou silou. Možno doplnit 3–5 % Carapils pro stabilitu pěny.",
            "chmel": "**Žatecký poloraný červeňák (Saaz)** – jemný aromatický chmel dodávající bylinné až kořenité aroma. Pro hořkost se používá např. Premiant či Sládek.",
            "voda": "**Měkká voda** s nízkým obsahem minerálů (vápník 30–50 ppm, nízké sírany i chloridy).",
            "kvasinky": "**Spodní kvašení** (*Saccharomyces pastorianus*, např. pivovarské husté kvasnice / W-34/70). Kvasí při 7–11 °C.",
            "tip": "U ležáku je klíčová čistota surovin a vyváženost – jakákoliv chyba v chuti se v jemném profilu snadno projeví."
        },
        "American IPA / APA": {
            "slad": "**Pale Ale slad (85–90 %)** jako základ, doplněný o karamelový slad (Caramalt 5–10 %) a pšeničný slad pro pěnu.",
            "chmel": "**Americké aromatické odrůdy** (Citra, Mosaic, Simcoe, Amarillo) s vysokým obsahem silic a alfa-kyselin pro výrazné citrusové a tropické tóny.",
            "voda": "**Tvrdší síranová voda** (vysoký poměr SO₄²⁻ : Cl⁻) pro zvýraznění suchosti a řízné hořkosti.",
            "kvasinky": "**Svrchní kvašení** (*Saccharomyces cerevisiae*, např. SafAle US-05). Čistý profil kvasinek nechává vyniknout chmel.",
            "tip": "Klíčem je pozdní chmelení (whirlpool) a studené chmelení (dry hopping) v závěru kvašení."
        },
        "Tmavý ležák / Stout": {
            "slad": "**Kombinace světlých a pražených sladů**: Mnichovský/Pale Ale slad + Carafa Special, pražený ječmen a čokoládový slad pro kávové a čokoládové tóny.",
            "chmel": "**Vyvážené chmelení**: U ležáku kořenité české chmely, u stoutu spíše neutrální hořké odrůdy (Magnum, Target).",
            "voda": "**Vyšší podíl chloridů** pro plnost a krémovitost. Voda musí mít dostatečnou alkalitu proti překyselení rmutu.",
            "kvasinky": "Spodní kvasinky (u tmavého ležáku) nebo svrchní anglické kmeny (např. S-04 pro Stout).",
            "tip": "Tmavé a pražené slady přidávej až v závěru rmutování nebo na vyslazování, pokud se chceš vyhnout přílišné kyselosti a drsné trpkosti."
        },
        "Německé pšeničné (Weizen)": {
            "slad": "**Minimálně 50 % pšeničného sladu** doplněného Plzeňským sladem.",
            "chmel": "**Jemné chmelení** (Hallertau Mittelfrüh, Tettnanger) s nízkou hořkostí (10–15 IBU), aby nepřebila esterový profil.",
            "voda": "**Středně měkká voda** s vyváženým poměrem minerálů.",
            "kvasinky": "**Specifické kvasinky pro Weizen** (např. SafAle WB-06, Munich Classic), které tvoří estery banánu (isoamyl acetát) a fenoly hřebíčku (4-VG).",
            "tip": "Pšeničný slad nemá pluchy – dbej na správnou teplotu při scezování a případně použij rýžové slupky proti ucpání síta."
        }
    }
    
    data = suroviny_data[zvoleny_styl]
    
    st.subheader("4 pilíře vybraného stylu:")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"🌾 **Slad:** {data['slad']}")
        st.markdown(f"🌿 **Chmel:** {data['chmel']}")
    with col2:
        st.markdown(f"🚰 **Voda:** {data['voda']}")
        st.markdown(f"🧫 **Kvasinky:** {data['kvasinky']}")
        
    st.warning(f"💡 **Tip sládka:** {data['tip']}")

    st.subheader("Mini-kvíz: Prověř si znalosti")
    with st.form("form_lekce1"):
        q1 = st.radio("Při jaké teplotě probíhá optimální kvašení spodně kvašeného českého ležáku?", ["18–22 °C", "7–11 °C", "0–2 °C"])
        q2 = st.radio("Která složka chmele poskytuje trvalou hořkost po dlouhém varu?", ["Silice a aroma oleje", "Izomerizované alfa-kyseliny", "Třísloviny z listů"])
        if st.form_submit_button("Vyhodnotit kvíz"):
            if q1 == "7–11 °C" and q2 == "Izomerizované alfa-kyseliny":
                st.success("🎉 Skvěle! Obě odpovědi jsou správné.")
                st.session_state.kurz["lessons"]["lekce1"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Něco není správně, zkus to znovu.")

    render_mentor(
        "Kupuj plzeňský slad z prověřených humnových nebo moderních sladoven. Vždy zkontroluj, zda není navlhlý.",
        "Skladování chmele v teple a na vzduchu vede k oxidaci alfa-kyselin (sýrový pach). Chmel patří vždy do mrazáku a vakuového obalu!"
    )

# ==========================================
# LEKCE 2: VODA A JEJÍ ÚPRAVA
# ==========================================
elif "2. Voda a její úprava" in selected_view:
    st.header("🚰 Lekce 2: Voda a její chemická úprava")
    st.info(f"🎯 Zvolený pivní styl pro úpravu vody: **{zvoleny_styl}**")
    
    st.markdown("Voda tvoří přes 90 % piva. Každý pivní styl vyžaduje odlišné minerální složení pro zvýraznění sladu nebo chmele.")
    
    profily = {
        "Český světlý ležák (Pilsner)": {
            "popis": "Extrémně měkká voda s minimem minerálů. Cílem je čistá, neulpívající a jemná hořkost s hladkým tělem.",
            "ca": "30–50 ppm",
            "mg": "5–10 ppm",
            "so4": "20–40 ppm",
            "cl": "30–50 ppm",
            "pomer": "1:1 až 1:1.2 (vyrovnaný / lehce pro chloridy)",
            "ph": "5.2 – 5.5",
            "tip": "Vyhni se vysokým síranům (sádrovci), jinak bude hořkost Žateckého poloraného červeňáku drsná a trpká.",
            "q2_q": "Proč se u plzeňského ležáku vyhýbáme vysokým dávkám sádrovce (síranů)?",
            "q2_opts": ["Protože by hořkost jemného žateckého chmele byla drsná a trpká", "Protože by pivo mělo málo alkoholu", "Protože by pivo nešlo stočit"],
            "q2_ans": "Protože by hořkost jemného žateckého chmele byla drsná a trpká"
        },
        "American IPA / APA": {
            "popis": "Tvrdší síranová voda. Vysoký obsah síranů zásadně podpoří suchost a ostrost moderní chmelové hořkosti.",
            "ca": "75–120 ppm",
            "mg": "10–20 ppm",
            "so4": "150–300 ppm",
            "cl": "50–75 ppm",
            "pomer": "2:1 až 4:1 (výrazně pro sírany)",
            "ph": "5.2 – 5.4",
            "tip": "Přidává se síran vápenatý (sádrovec / CaSO4) pro vysušení profilu a vytažení pryskyřičných a citrusových tónů chmele.",
            "q2_q": "Který iont se přidává (ve formě sádrovce) pro suchou a ostrou hořkost u IPA?",
            "q2_opts": ["Síran (SO₄²⁻)", "Chlorid (Cl⁻)", "Sodík (Na⁺)"],
            "q2_ans": "Síran (SO₄²⁻)"
        },
        "Tmavý ležák / Stout": {
            "popis": "Voda s vyšším podílem chloridů pro podporu plnosti a zaoblení pražených tónů. Tmavé slady přirozeně sráží pH.",
            "ca": "50–80 ppm",
            "mg": "10–20 ppm",
            "so4": "40–60 ppm",
            "cl": "100–150 ppm",
            "pomer": "1:2 (výrazně pro chloridy)",
            "ph": "5.4 – 5.6",
            "tip": "Pražené a karamelové slady jsou kyselé. Pozor na přílišný pokles pH pod 5.2, často není potřeba žádná kyselina.",
            "q2_q": "Který poměr minerálů preferujeme u tmavých piv pro plné a jemné tělo?",
            "q2_opts": ["Převahu chloridů (Cl⁻)", "Extrémní převahu síranů (SO₄²⁻)", "Vodu bez jakýchkoliv minerálů"],
            "q2_ans": "Převahu chloridů (Cl⁻)"
        },
        "Německé pšeničné (Weizen)": {
            "popis": "Středně měkká, vyvážená voda. V popředí stojí esterový profil kvasinek (banány a hřebíček), nikoliv minerály.",
            "ca": "40–70 ppm",
            "mg": "5–15 ppm",
            "so4": "40–60 ppm",
            "cl": "40–60 ppm",
            "pomer": "1:1 (vyrovnaný poměr)",
            "ph": "5.2 – 5.4",
            "tip": "Pšeničný slad nemá pluchy, takže riziko vyluhování drsných tříslovin při vyšším pH je menší, ale enzymy vyžadují stabilitu.",
            "q2_q": "Jaký poměr síranů a chloridů je ideální pro pšeničné pivo?",
            "q2_opts": ["Vyvážený poměr cca 1:1", "10:1 pro sírany", "1:5 pro chloridy"],
            "q2_ans": "Vyvážený poměr cca 1:1"
        }
    }
    
    profil = profily[zvoleny_styl]
    st.info(f"💡 **Profil pro {zvoleny_styl}:** {profil['popis']}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vápník (Ca²⁺)", profil["ca"])
    col2.metric("Síran (SO₄²⁻)", profil["so4"])
    col3.metric("Chlorid (Cl⁻)", profil["cl"])
    col4.metric("Poměr SO₄²⁻ : Cl⁻", profil["pomer"])
    
    st.markdown(f"**Cílové pH rmutu při 20 °C:** `{profil['ph']}`")
    st.warning(f"📌 **Doporučení sládka:** {profil['tip']}")
    st.divider()
    
    st.subheader(f"📝 Kvíz: Voda pro {zvoleny_styl}")
    with st.form("quiz_voda"):
        q1 = st.radio("Jaké je ideální cílové pH rmutu pro optimální práci enzymů?", ["6.2 – 6.8", "5.2 – 5.5", "4.0 – 4.5"])
        q2 = st.radio(profil["q2_q"], profil["q2_opts"])
        submit_voda = st.form_submit_button("Vyhodnotit odpovědi")
        
        if submit_voda:
            body = 0
            if q1 == "5.2 – 5.5": body += 1
            if q2 == profil["q2_ans"]: body += 1
                
            if body == 2:
                st.success(f"Výborně! 2/2 správně pro styl {zvoleny_styl} 🎉")
                st.session_state.kurz["lessons"]["lekce2"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning(f"Máš {body}/2 správně. Prohlédni si doporučení výše a zkus to znovu.")

# ==========================================
# LEKCE 3: RMUTOVÁNÍ & ENZYMY
# ==========================================
elif "3. Rmutování & Enzymy" in selected_view:
    if "Pilsner" in zvoleny_styl:
        st.header("🔥 Lekce 3: Dekokční rmutování a enzymatika")
    elif "IPA" in zvoleny_styl:
        st.header("🔥 Lekce 3: Infuzní rmutování a enzymatika")
    elif "Weizen" in zvoleny_styl:
        st.header("🔥 Lekce 3: Rmutování pšeničného piva a enzymatika")
    else:
        st.header("🔥 Lekce 3: Rmutovací profily pro tmavá piva a enzymatika")

    st.markdown("""
    Rmutování je enzymatická přeměna sladových škrobů:
    * **Beta-amyláza (62–65 °C):** Tvorba maltózy $\\rightarrow$ vyšší prokvašení a sušší profil.
    * **Alfa-amyláza (70–75 °C):** Tvorba nezkvasitelných dextrinů $\\rightarrow$ plnost těla a sladovost.
    * **Odrmutování (78 °C):** Zastavení enzymů a snížení viskozity pro scezování.
    """)

    st.divider()

    if "IPA" in zvoleny_styl:
        st.subheader("⚙️ Rmutovací technologie pro American IPA / APA")
        st.warning("💡 **Pravidlo pro IPA:** U amerických piv se dekokce nepoužívá. Cílem je jednoduchá infuze pro dosažení suchého těla, které dá vyniknout chmelu.")
        dopstupne_metody = [
            "Jednokroková infuze na vyšší prokvašení (65 °C)",
            "Dvoukroková infuze s dextrinovou pauzou (64 °C + 71 °C)"
        ]
    elif "Pilsner" in zvoleny_styl:
        st.subheader("⚙️ Rmutovací technologie pro Český ležák")
        dopstupne_metody = [
            "Dvourmutová dekokce (Klasický český ležák)",
            "Jednormutová dekokce (Rychlejší moderní ležák)",
            "Třírmutová dekokce (Historický tradiční plzeňský postup)"
        ]
    elif "Weizen" in zvoleny_styl:
        st.subheader("⚙️ Rmutovací technologie pro Pšeničné pivo")
        dopstupne_metody = [
            "Infuze s ferulovou pauzou (44 °C na hřebíček + 63 °C + 72 °C)",
            "Jednormutová dekokce pro Weizen"
        ]
    else:
        st.subheader("⚙️ Rmutovací technologie pro Stout / Tmavá piva")
        dopstupne_metody = [
            "Jednokroková infuze na plné tělo (67–69 °C)",
            "Dvourmutová dekokce (pro Tmavý ležák)"
        ]

    metoda = st.radio(
        "Zvol technologický postup:",
        dopstupne_metody,
        key=f"rmut_metoda_{zvoleny_styl}"
    )

    postupy_data = {
        "Jednokroková infuze na vyšší prokvašení (65 °C)": {
            "casy": [0, 10, 70, 80, 90],
            "teploty": [65, 65, 65, 78, 78],
            "kroky": [
                "**1. Vystření (65 °C):** Slad se rozmíchá ve vodě o teplotě cca 71 °C.",
                "**2. Hlavní infuzní pauza (60 min):** Teplota 65 °C dává optimální poměr mezi maltózou a dextriny se sušším zakončením.",
                "**3. Mash-out (78 °C):** Ohřev celé nádoby na 78 °C před scezováním."
            ],
            "vyhody": "Žádné povařování rmutu. Zachovává velmi světlou barvu a lehký profil pro aromatické americké chmely."
        },
        "Dvoukroková infuze s dextrinovou pauzou (64 °C + 71 °C)": {
            "casy": [0, 10, 50, 60, 85, 95, 105],
            "teploty": [64, 64, 71, 71, 71, 78, 78],
            "kroky": [
                "**1. Vystření (64 °C):** 40 minut na tvorbu zkvasitelných cukrů.",
                "**2. Přímý ohřev na 71 °C:** 25 minut pro stabilizaci pěny a lehké tělo.",
                "**3. Odrmutování (78 °C):** 10 minut před scezením."
            ],
            "vyhody": "Přesná kontrola nad suchostí a stabilitou pěny u silnějších piv typu Double IPA."
        },
        "Dvourmutová dekokce (Klasický český ležák)": {
            "casy": [0, 15, 25, 40, 50, 60, 70, 80, 90, 100, 110, 120],
            "teploty": [37, 52, 63, 100, 63, 63, 100, 72, 72, 78, 78, 78],
            "kroky": [
                "**1. Vystření na 37–52 °C:** Bílkovinná pauza.",
                "**2. Odběr 1. rmutu (1/3 hustého podílu):** Ohřev na 63 °C, 72 °C a var 20 min v rmutovacím kotli.",
                "**3. První vyrovnání na 63 °C:** Vroucí rmut se vrátí k řídkému dílu $\\rightarrow$ teplota stoupne na 63 °C.",
                "**4. Odběr 2. rmutu (1/3 hustého podílu):** Ohřev na 72 °C a var 15 min.",
                "**5. Druhé vyrovnání na 72 °C:** Návrat povařeného rmutu $\\rightarrow$ ohřev na 72 °C.",
                "**6. Odrmutování na 78 °C.**"
            ],
            "vyhody": "Typická chlebnatost, plnost a tvorba melanoidinů pro zlatavý český ležák."
        },
        "Jednormutová dekokce (Rychlejší moderní ležák)": {
            "casy": [0, 15, 30, 45, 55, 65, 80, 90, 100],
            "teploty": [52, 52, 63, 63, 100, 72, 72, 78, 78],
            "kroky": [
                "**1. Vystření na 52–63 °C.**",
                "**2. Odběr 1/3 hustého díla:** Povaření 15 minut.",
                "**3. Vyrovnání na 72 °C:** Návrat vroucího rmutu pro finální zcukření.",
                "**4. Mash-out (78 °C).**"
            ],
            "vyhody": "Zkrácení varného dne při zachování dekokčního charakteru."
        },
        "Třírmutová dekokce (Historický tradiční plzeňský postup)": {
            "casy": [0, 15, 25, 40, 50, 65, 75, 90, 100, 115, 125, 140, 150],
            "teploty": [35, 35, 63, 100, 52, 63, 100, 63, 63, 100, 72, 78, 78],
            "kroky": [
                "**1. Studené vystření (35 °C).**",
                "**2. Tři po sobě jdoucí odběry a vary rmutů (1/3):** Postupný ohřev na 52 °C, 63 °C a 72 °C.",
                "**3. Mash-out na 78 °C.**"
            ],
            "vyhody": "Historická metoda pro málo rozluštěné slady. Maximální extrakt a hluboká barva."
        },
        "Infuze s ferulovou pauzou (44 °C na hřebíček + 63 °C + 72 °C)": {
            "casy": [0, 20, 45, 55, 75, 85, 95],
            "teploty": [44, 44, 63, 63, 72, 72, 78],
            "kroky": [
                "**1. Ferulová pauza (44 °C, 15–20 min):** Uvolnění kyseliny ferulové pro hřebíčkové aroma.",
                "**2. Maltózová pauza (63 °C, 30 min):** Tvorba cukrů.",
                "**3. Dextrinová pauza (72 °C, 20 min):** Pěnivost a tělo.",
                "**4. Mash-out (78 °C).**"
            ],
            "vyhody": "Klíčový krok pro autentické aroma bavorského pšeničného piva."
        },
        "Jednormutová dekokce pro Weizen": {
            "casy": [0, 15, 30, 45, 55, 65, 80, 90, 100],
            "teploty": [44, 44, 63, 63, 100, 72, 72, 78, 78],
            "kroky": [
                "**1. Vystření na 44 °C.**",
                "**2. Odběr 1/3 hustého díla a var 10 min.**",
                "**3. Vyrovnání na 72 °C a odrmutování na 78 °C.**"
            ],
            "vyhody": "Zvýraznění plnosti a rustikálního charakteru pšeničného piva."
        },
        "Jednokroková infuze na plné tělo (67–69 °C)": {
            "casy": [0, 10, 70, 80, 90],
            "teploty": [68, 68, 68, 78, 78],
            "kroky": [
                "**1. Vystření na 68 °C:** Vyšší teplota podporuje alfa-amylázu.",
                "**2. Infuze (60 min):** Vzniká vyšší podíl nezkvasitelných cukrů pro hutné a krémové tělo Stoutu.",
                "**3. Mash-out (78 °C).**"
            ],
            "vyhody": "Dává plné, sametové tělo vyvažující praženou hořkost černých sladů."
        },
        "Dvourmutová dekokce (pro Tmavý ležák)": {
            "casy": [0, 15, 25, 40, 50, 60, 70, 80, 90, 100, 110, 120],
            "teploty": [37, 52, 63, 100, 63, 63, 100, 72, 72, 78, 78, 78],
            "kroky": [
                "**1. Vystření základních světlých a mnichovských sladů.**",
                "**2. Dva povařené rmuty pro plné tělo.**",
                "**3. Tmavé a barvicí slady se přidávají až před scezením**, aby pivo nebylo trpké."
            ],
            "vyhody": "Kulatá, jemná sladovost bez drsné spálené pachuti."
        }
    }

    d = postupy_data[metoda]

    st.markdown("#### 📋 Postup krok za krokem:")
    for krok in d["kroky"]:
        st.markdown(krok)

    st.success(f"💎 **Charakteristika:** {d['vyhody']}")

    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(d["casy"], d["teploty"], marker='o', color='#E65100', linewidth=2.5, label='Teplota díla')
    ax.set_title(f"Teplotní diagram: {metoda.split('(')[0].strip()}", fontsize=11, fontweight='bold')
    ax.set_xlabel("Čas (minuty)")
    ax.set_ylabel("Teplota (°C)")
    ax.set_ylim(30, 105)
    ax.axhline(63, color='#4CAF50', linestyle='--', alpha=0.6, label='Beta-amyláza (63 °C)')
    ax.axhline(72, color='#2196F3', linestyle='--', alpha=0.6, label='Alfa-amyláza (72 °C)')
    if max(d["teploty"]) >= 100:
        ax.axhline(100, color='#D32F2F', linestyle=':', alpha=0.6, label='Var rmutu (100 °C)')
    ax.legend(loc='lower right', fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.35)
    st.pyplot(fig)

# ==========================================
# LEKCE 4: SCEZOVÁNÍ & RECIRKULACE
# ==========================================
elif "4. Scezování & Recirkulace" in selected_view:
    st.header("🪣 Lekce 4: Scezování, vyslazování a recirkulace")
    st.info(f"🎯 Specifika filtrace pro styl: **{zvoleny_styl}**")

    scezovani_data = {
        "Český světlý ležák (Pilsner)": {
            "pluchy": "Plzeňský ječmenný slad má ideální podíl pluch, které tvoří přirozené filtrační lože.",
            "teplota": "Vyslazovací voda musí mít **75–78 °C**. Vyšší teplota (nad 80 °C) vyluhuje třísloviny a křemičitany z pluch.",
            "postup": "Pomalé vytvoření filtračního koláče, recirkulace prvních kalných podílů mladiny a plynulý odtok.",
            "varovani": "Nespěchat s odtokem, aby se filtrační koláč nestlačil a neucpal."
        },
        "American IPA / APA": {
            "pluchy": "Vysoký podíl základního ječmenného sladu zajišťuje bezproblémovou filtraci.",
            "teplota": "Standardní vyslazování při **76–78 °C**.",
            "postup": "Důraz na čistý přechod do chmelovaru bez přenášení zbytečných kalů, které by kalily chmelové aroma.",
            "varovani": "Při použití vyššího podílu ovesných/pšeničných vloček pro styl NEIPA může dojít ke zpomalení toku."
        },
        "Tmavý ležák / Stout": {
            "pluchy": "Pražená zrna jsou křehčí a mohou tvořit jemný prach.",
            "teplota": "Vyslazování při **75–77 °C**.",
            "postup": "Pokud se pražené slady přidávají až na mash-out/vyslazování pro barvu bez trpkosti, sypou se přímo na horní vrstvu filtračního lože.",
            "varovani": "Příliš horká voda v závěru může z pražených zrn uvolnit svíravou a drsnou popelavost."
        },
        "Německé pšeničné (Weizen)": {
            "pluchy": "⚠️ **Kritické:** Pšeničný slad **nemá pluchy** a obsahuje hodně bílkovin a glukanů, které tvoří husté těsto.",
            "teplota": "Striktně držet teplotu mash-outu **78 °C** pro snížení viskozity mladiny.",
            "postup": "Doporučuje se přidat rýžové slupky (cca 5 % sypání) pro vytvoření umělého filtračního lože.",
            "varovani": "Nebezpečí ucpání scezovacího síta (Stuck Mash) při rychlém odtoku."
        }
    }

    sc = scezovani_data[zvoleny_styl]
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"🌾 **Filtrační lože:** {sc['pluchy']}")
        st.markdown(f"🌡️ **Teplota vyslazování:** {sc['teplota']}")
    with col2:
        st.markdown(f"⚙️ **Doporučený postup:** {sc['postup']}")
        st.warning(f"🚨 **Riziko sládka:** {sc['varovani']}")

# ==========================================
# LEKCE 5: KVAŠENÍ & MANAGEMENT KVASINEK
# ==========================================
elif "5. Kvašení & Diacetyl" in selected_view:
    st.header("🧪 Lekce 5: Kvašení, pitching rate a vedlejší produkty")
    st.info(f"🎯 Režim kvašení pro styl: **{zvoleny_styl}**")
    
    kvaseni_data = {
        "Český světlý ležák (Pilsner)": {
            "typ": "Spodní kvašení (*Saccharomyces pastorianus*, např. pivovarské husté kvasnice / W-34/70)",
            "teplota": "7–10 °C (Čerstvé husté kvasnice z pivovaru kvasí čistě už od 7 °C; sušené kmeny vyžadují cca 9–11 °C)",
            "pitching": "**1.5–2.0 milionu buněk / ml / °P** (cca 0.5–1 litr hustých pivovarských kvasnic nebo minimálně 2 balíčky sušených na 20 l mladiny).",
            "diacetyl": "**Diacetylová pauza:** Na konci kvašení (při cca 3–3.5 °P) nechat teplotu vystoupat na 12–14 °C pro spolehlivé odbourání máslového diacetylu.",
            "specifika": "Při 7 °C trvá hlavní kvašení 10–14 dní. Výsledkem je křišťálově čistý chuťový profil bez cizích pachutí.",
            "q1_q": "Kolik balíčků suchých kvasinek (11.5 g) je potřeba pro 20 litrů 12° ležáku?",
            "q1_opts": ["Pouze 1/2 balíčku", "1 balíček", "Minimálně 2 balíčky (pro ležácký pitching rate)"],
            "q1_ans": "Minimálně 2 balíčky (pro ležácký pitching rate)",
            "q2_q": "Kdy zahajujeme diacetylovou pauzu (Diacetyl rest)?",
            "q2_opts": ["Až po 4 týdnech v KEGu", "Ke konci hlavního kvašení při dokvašování posledních 20–25 % cukrů", "Při vystírání sladu"],
            "q2_ans": "Ke konci hlavního kvašení při dokvašování posledních 20–25 % cukrů"
        },
        "American IPA / APA": {
            "typ": "Svrchní kvašení (*Saccharomyces cerevisiae*, např. US-05)",
            "teplota": "18–20 °C",
            "pitching": "**0.75 milionu buněk / ml / °P** (stačí **1 balíček** sušených kvasinek 11.5 g na 20 l mladiny).",
            "diacetyl": "Díky vyšší teplotě kvasinky odbourají diacetyl přirozeně a rychle během hlavního kvašení.",
            "specifika": "**Studené chmelení (Dry Hopping):** Chmel se přidává přímo do kvasné nádoby ke konci bouřlivého kvašení (na 2–4 dny) při 14–16 °C.",
            "q1_q": "Jaký pitching rate (dávka kvasinek) stačí pro svrchně kvašenou IPA?",
            "q1_opts": ["Standardní dávka (cca 1 balíček 11.5 g na 20 l)", "Extrémní dávka (3 balíčky)", "Není potřeba očkovat"],
            "q1_ans": "Standardní dávka (cca 1 balíček 11.5 g na 20 l)",
            "q2_q": "Kdy se typicky provádí Dry Hopping (studené chmelení)?",
            "q2_opts": ["Při varu v kotli", "Ke konci hlavního kvašení před stočením", "Před zahájením rmutování"],
            "q2_ans": "Ke konci hlavního kvašení před stočením"
        },
        "Tmavý ležák / Stout": {
            "typ": "Dle receptury: Spodní (10 °C) pro tmavý ležák nebo Svrchní (18–20 °C, např. S-04) pro Stout",
            "teplota": "10 °C (ležák) / 19 °C (stout)",
            "pitching": "Záleží na kvasinkách: 1.5 mil. pro ležácký kmen, 0.75 mil. pro stoutové svrchní kmeny.",
            "diacetyl": "U tmavých piv může mírný diacetyl působit sladce/karamelově, ale ve větším množství je vadou. Dodržuj stabilní dokvašení.",
            "specifika": "Tmavé slady okyselují prostředí, proto kvašení nastupuje rychle. Pozor na odvětrání případných sirných tónů.",
            "q1_q": "Jak působí tmavé a pražené slady na pH mladiny během kvašení?",
            "q1_opts": ["Přirozeně okyselují prostředí (snižují pH)", "Zvyšují zásaditost", "Nemají žádný vliv na pH"],
            "q1_ans": "Přirozeně okyselují prostředí (snižují pH)",
            "q2_q": "Jaké kvasinky se nejčastěji používají pro tradiční suchý Stout (Dry Stout)?",
            "q2_opts": ["Svrchní anglické kvasinky (např. S-04)", "Kvasinky na divoké kvašení", "Pouze plzeňské spodní kvasinky"],
            "q2_ans": "Svrchní anglické kvasinky (např. S-04)"
        },
        "Německé pšeničné (Weizen)": {
            "typ": "Specifické svrchní kvasinky (*SafAle WB-06*, *Munich Classic*)",
            "teplota": "18–22 °C (Řízený profil esterů a fenolů)",
            "pitching": "**Podmnožení (Underpitching):** Používá se standardní až mírně nižší dávka (1 balíček na 20 l), aby kvasinky vyprodukovaly více žádoucích esterů.",
            "diacetyl": "Rychlé odbourání při 20 °C během 4–5 dnů.",
            "specifika": "**Řízení chutí teplotou:** Nižší teplota (18 °C) = hřebíček (fenol 4-VG). Vyšší teplota (22 °C) = banán (isoamyl acetát).",
            "q1_q": "Jak ovlivní vyšší kvasná teplota (cca 22 °C) profil pšeničného piva?",
            "q1_opts": ["Zvýrazní banánové aroma (estery)", "Zvýrazní hřebíčkové aroma", "Pivo ztratí pěnu"],
            "q1_ans": "Zvýrazní banánové aroma (estery)",
            "q2_q": "Proč se u pšeničných piv často záměrně nepředávkují kvasinky (lehký underpitching)?",
            "q2_opts": ["Aby kvasinky při růstu vytvořily více aromatických esterů", "Aby se ušetřilo na surovinách", "Aby pivo nemělo alkohol"],
            "q2_ans": "Aby kvasinky při růstu vytvořily více aromatických esterů"
        }
    }
    
    k = kvaseni_data[zvoleny_styl]
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"🧫 **Typ kvasinek:** {k['typ']}")
        st.markdown(f"🌡️ **Doporučená teplota:** `{k['teplota']}`")
        st.markdown(f"⚖️ **Dávkování (Pitching rate):** {k['pitching']}")
    with col2:
        st.markdown(f"🧈 **Diacetyl & regulace:** {k['diacetyl']}")
        st.markdown(f"💡 **Specifika kvašení:** {k['specifika']}")
        
    st.divider()
    
    st.subheader(f"📝 Kvíz: Kvašení pro {zvoleny_styl}")
    with st.form("quiz_kvaseni"):
        ans1 = st.radio(k["q1_q"], k["q1_opts"])
        ans2 = st.radio(k["q2_q"], k["q2_opts"])
        submit_kvas = st.form_submit_button("Vyhodnotit lekci 5")
        
        if submit_kvas:
            score = 0
            if ans1 == k["q1_ans"]: score += 1
            if ans2 == k["q2_ans"]: score += 1
                
            if score == 2:
                st.success(f"Výborně! {score}/2 správně pro {zvoleny_styl} 🎉")
                st.session_state.kurz["lessons"]["lekce5"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning(f"Získal jsi {score}/2 bodů. Zkontroluj doporučení výše a zkus to znovu.")

# ==========================================
# LEKCE 6: ZRÁNÍ & NASYCENÍ V KEGU
# ==========================================
elif "6. Ležákování & KEG" in selected_view:
    if "Pilsner" in zvoleny_styl or "Tmavý ležák" in zvoleny_styl:
        st.header("❄️ Lekce 6: Ležákování v chladu a nasycení v KEGu")
    else:
        st.header("❄️ Lekce 6: Zrání piva, Cold Crash a nasycení v KEGu")
        
    st.info(f"🎯 Profil zrání a sycení pro styl: **{zvoleny_styl}**")

    lezak_data = {
        "Český světlý ležák (Pilsner)": {
            "teplota": "1–3 °C (sklepní zrání)",
            "doba": "Minimálně **4–6 týdnů** (pravidlo: 1 týden na každý 1° Plato).",
            "syceni": "Střední nasycení: **2.3–2.5 objemu CO₂** (tlak cca 0.8–1.0 bar při 4 °C).",
            "cisteni": "Pomalé přirozené sedimentování kvasnic a vysrážení chladového zákalu (*chill haze*)."
        },
        "American IPA / APA": {
            "teplota": "Cold Crash: 2–4 °C (krátce na 2–3 dny před stáčením)",
            "doba": "**Krátká (1–2 týdny)**. Pivo se pije čerstvé, chmelové aroma s časem rychle degraduje!",
            "syceni": "Vyšší říz: **2.4–2.7 objemu CO₂** pro podporu uvolňování chmelových silic.",
            "cisteni": "Rychlé vyčeření chmelových pelet po studeném chmelení (Dry Hop)."
        },
        "Tmavý ležák / Stout": {
            "teplota": "Ležák 1–3 °C / Stout 10–12 °C",
            "doba": "**4–8 týdnů**. Tmavé pražené tóny potřebují čas na zakulacení a zjemnění.",
            "syceni": "U Stoutu spíše nižší nasycení: **1.8–2.2 objemu CO₂** pro krémovost (případně směs N₂/CO₂).",
            "cisteni": "Přirozené zrání, zákal není díky tmavé barvě patrný."
        },
        "Německé pšeničné (Weizen)": {
            "teplota": "10–12 °C (nechladit na bod mrazu, aby nevymizely kvasinky)",
            "doba": "**2–3 týdny**. Pije se velmi mladé a svěží.",
            "syceni": "Vysoké nasycení: **2.8–3.3 objemu CO₂** (tlak cca 1.4–1.6 bar při 6 °C) – typický vysoký říz a pěna.",
            "cisteni": "Zákal tvořený kvasinkami a bílkovinami je **žádoucí**."
        }
    }

    lz = lezak_data[zvoleny_styl]
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.markdown(f"🌡️ **Teplotní režim:** {lz['teplota']}")
        st.markdown(f"⏳ **Délka zrání:** {lz['doba']}")
    with col_l2:
        st.markdown(f"🫧 **Cílové nasycení CO₂:** {lz['syceni']}")
        st.markdown(f"✨ **Čistota a stabilita:** {lz['cisteni']}")

    st.divider()
    st.subheader("📝 Kvíz: Správa CO₂ v KEGu")
    with st.form("quiz_keg"):
        q_keg = st.radio(
            "Proč před plněním Corny KEGu vytěsňujeme vzduch plynem CO₂ (sanitace plynem)?",
            [
                "Abychom sud ochladili",
                "Abychom zabránili oxidaci piva (chuti po mokrém kartonu a degradaci chmelu)",
                "Aby se zvýšila pěnivost mladiny"
            ]
        )
        if st.form_submit_button("Odevzdat test"):
            if q_keg == "Abychom zabránili oxidaci piva (chuti po mokrém kartonu a degradaci chmelu)":
                st.success("Správně! Kyslík je největší nepřítel hotového piva 🎉")
                st.session_state.kurz["lessons"]["lekce6"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Zkus to znovu. Klíčem je ochrana před vzdušným kyslíkem.")

# ==========================================
# LEKCE 7: SENZORIKA & VADY
# ==========================================
elif "7. Senzorika & Pivní vady" in selected_view:
    st.header("👃 Lekce 7: Senzorika piva a pivní vady (Off-flavors)")
    st.info(f"🎯 Senzorický profil a typická úskalí pro styl: **{zvoleny_styl}**")

    senzorika_data = {
        "Český světlý ležák (Pilsner)": {
            "vady": [
                "🧈 **Diacetyl:** Máslová příchuť. V ležáku je povolena jen nepatrná stopa, nesmí dominovat.",
                "🌽 **DMS (Dimetylsulfid):** Vařená kukuřice či zelenina. Vzniká slabým chmelovarem nebo pomalým chlazením.",
                "📦 **Oxidace:** Chuť mokrého kartonu či medu způsobená stykem se vzduchem."
            ],
            "otazka": "Co je hlavní příčinou vzniku DMS (kukuřičné příchuti) v ležáku?",
            "moznosti": [
                "Slabý chmelovar se zakrytou poklicí bez odparu a pomalé chlazení mladiny",
                "Kvašení při příliš nízké teplotě",
                "Příliš mnoho českého chmele"
            ],
            "spravne": "Slabý chmelovar se zakrytou poklicí bez odparu a pomalé chlazení mladiny"
        },
        "American IPA / APA": {
            "vady": [
                "📦 **Oxidace:** Extrémní nepřítel IPA. Způsobuje zhnědnutí barvy a ztrátu svěžího ovocného aroma.",
                "🦨 **Světelná vada (Lightstruck):** Zápach po skunkovi při kontaktu chmelových iso-alfa kyselin se světlem.",
                "🌿 **Travnatost / Trpkost:** Příliš dlouhé studené chmelení (nad 4–5 dní) nebo vyluhování pelet."
            ],
            "otazka": "Jak se projeví oxidace u moderní chmelené IPA?",
            "moznosti": [
                "Ztmavnutím barvy a ztrátou citrusového/tropického aroma na úkor chuti po kartonu",
                "Zvýšením kvasné teploty",
                "Okamžitým zkysnutím piva na ocet"
            ],
            "spravne": "Ztmavnutím barvy a ztrátou citrusového/tropického aroma na úkor chuti po kartonu"
        },
        "Tmavý ležák / Stout": {
            "vady": [
                "🔥 **Spálená hořkost / Popel:** Nesprávné rmutování tmavých sladů.",
                "🍏 **Acetaldehyd:** Chuť zelených jablek z nedokvašeného piva.",
                "🧀 **Kyselina isovalerová:** Zápach po starém sýru ze zkaženého starého chmele."
            ],
            "otazka": "Čím vzniká nepřirozeně drsná a spálená svíravost u Stoutu?",
            "moznosti": [
                "Příliš dlouhým varem a vyluhováním jemně mletých černých sladů v kyselém prostředí",
                "Použitím kvasnic S-04",
                "Nízkým obsahem alkoholu"
            ],
            "spravne": "Příliš dlouhým varem a vyluhováním jemně mletých černých sladů v kyselém prostředí"
        },
        "Německé pšeničné (Weizen)": {
            "vady": [
                "💊 **Medicínská chuť (Chlorfenoly):** Vzniká reakcí chloru z vody s kvasinkami.",
                "🧀 **Tukové/Mýdlové tóny:** Stárnutí kvasinek v lahvi.",
                "💡 **Poznámka k pšenici:** Výrazný banán (isoamyl acetát) a hřebíček (4-VG) zde **nejsou vadou**, ale žádaným stylem!"
            ],
            "otazka": "Která z těchto vůní je u pravého pšeničného piva (Weizen) ŽÁDOUCÍ?",
            "moznosti": [
                "Banány (estery) a hřebíček (fenoly)",
                "Vařená kukuřice a zelenina (DMS)",
                "Mokrý karton (oxidace)"
            ],
            "spravne": "Banány (estery) a hřebíček (fenoly)"
        }
    }

    sn = senzorika_data[zvoleny_styl]
    for vada in sn["vady"]:
        st.markdown(vada)

    st.divider()
    st.subheader(f"📝 Kvíz: Senzorika pro {zvoleny_styl}")
    with st.form("quiz_vady"):
        q_vada = st.radio(sn["otazka"], sn["moznosti"])
        if st.form_submit_button("Vyhodnotit test"):
            if q_vada == sn["spravne"]:
                st.success("Výborně! Správná odpověď 🎉")
                st.session_state.kurz["lessons"]["lekce7"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Špatná odpověď, pročti si vady výše a zkus to znovu.")

# ==========================================
# LEKCE 8: RECEPTURY & TVORBA PIVA
# ==========================================
elif "8. Receptury & Tvorba" in selected_view:
    st.header(f"📜 Lekce 8: Stavba receptury – {zvoleny_styl}")
    st.info(f"🎯 Normy a poměry surovin pro styl: **{zvoleny_styl}**")

    recept_data = {
        "Český světlý ležák (Pilsner)": {
            "sypani": "* **Základ (95–100 %):** Český plzeňský slad\n* **Doplňky (0–5 %):** Mnichovský slad nebo Carapils",
            "chmeleni": "* **1. dávka (60–90 min):** 60 % IBU (hořkost – např. Premiant/ŽPČ)\n* **2. dávka (20–30 min):** 30 % IBU (chuť – ŽPČ)\n* **3. dávka (0–5 min / whirlpool):** 10 % IBU (aroma – ŽPČ)",
            "bugu": "**0.70 až 0.85** (harmonická, vyšší pitelná hořkost)",
            "otazka": "Jaký poměr BU:GU (hořkost ku hustotě mladiny) je typický pro poctivý český ležák?",
            "moznosti": ["0.10 až 0.20 (téměř bez hořkosti)", "0.70 až 0.85 (střední až vyšší harmonická hořkost)", "1.50 až 2.00 (extrémní hořkost)"],
            "spravne": "0.70 až 0.85 (střední až vyšší harmonická hořkost)"
        },
        "American IPA / APA": {
            "sypani": "* **Základ (85–90 %):** Pale Ale slad\n* **Doplňky (10–15 %):** Pšeničný slad, Caramalt / Munich",
            "chmeleni": "* **1. dávka (60 min):** 25 % IBU (čistá hořkost – Magnum/Warrior)\n* **2. dávka (Whirlpool 80 °C):** 40 % IBU + masivní aroma (Citra, Mosaic)\n* **3. dávka (Dry Hop 3 dny):** 0 IBU, čisté silice",
            "bugu": "**0.85 až 1.20** (výrazná, suchá a čistá hořkost)",
            "otazka": "Kde vzniká největší část ovocného aromatu u moderní IPA?",
            "moznosti": ["Při varu v prvních 10 minutách", "Ve whirlpoolu při 80 °C a při studeném chmelení (Dry Hopping)", "Z praženého sladu"],
            "spravne": "Ve whirlpoolu při 80 °C a při studeném chmelení (Dry Hopping)"
        },
        "Tmavý ležák / Stout": {
            "sypani": "* **Základ (70–80 %):** Plzeňský / Pale Ale slad + Mnichovský\n* **Pražené a karamelové slady (15–20 %):** Carafa, Pražený ječmen, Čokoládový slad",
            "chmeleni": "* **1. dávka (60 min):** 80 % IBU (neutrální hořkost)\n* **2. dávka (15 min):** 20 % IBU pro vyvážení sladkosti",
            "bugu": "**0.50 až 0.75** (hořkost je doplněna praženými slady)",
            "otazka": "Proč se u stoutů a tmavých piv používá spíše neutrální chmel?",
            "moznosti": ["Aby nepřebíjel kávové a čokoládové aroma pražených sladů", "Protože aromatický chmel v tmavém pivu nefunguje", "Aby pivo nemělo pěnu"],
            "spravne": "Aby nepřebíjel kávové a čokoládové aroma pražených sladů"
        },
        "Německé pšeničné (Weizen)": {
            "sypani": "* **Základ (50–70 %):** Pšeničný slad světlý\n* **Doplněk (30–50 %):** Plzeňský slad",
            "chmeleni": "* **1. dávka (60 min):** 90 % IBU (jemný německý chmel na nízkých 12–15 IBU)\n* **Pozdní chmelení:** Pouze minimální nebo žádné",
            "bugu": "**0.25 až 0.35** (velmi nízká hořkost, v chuti dominují kvasinky)",
            "otazka": "Jaká je typická hodnota hořkosti (IBU) u klasického pšeničného piva (Weizen)?",
            "moznosti": ["Extrémní (50–70 IBU)", "Velmi nízká a jemná (10–15 IBU)", "Nulová"],
            "spravne": "Velmi nízká a jemná (10–15 IBU)"
        }
    }

    rc = recept_data[zvoleny_styl]
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown(f"🌾 **Skladba sypání:**\n{rc['sypani']}")
        st.markdown(f"⚖️ **Poměr hořkosti a hustoty (BU:GU):** `{rc['bugu']}`")
    with col_r2:
        st.markdown(f"🌿 **Rozvrh chmelení:**\n{rc['chmeleni']}")

    st.divider()
    st.subheader("📝 Kvíz: Stavba receptury")
    with st.form("quiz_recept"):
        q_rec = st.radio(rc["otazka"], rc["moznosti"])
        if st.form_submit_button("Odevzdat"):
            if q_rec == rc["spravne"]:
                st.success("Správně! Recepturu máš v malíku 🎉")
                st.session_state.kurz["lessons"]["lekce8"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Zkus to znovu podle parametrů výše.")

# =============================================================================
# LEKCE 9 & 10: CHECKLIST & ZÁVĚREČNÁ VÁRKA
# =============================================================================
elif selected_view == "📋 9 & 10. Checklist & Várka":
    st.header("Lekce 9 & 10: Sládkův checklist, Várka a Certifikát")
    
    tab_c1, tab_c2, tab_c3 = st.tabs(["📋 Checklist varného dne", "📓 Protokol várky", "🎓 Certifikát sládka"])
    
    with tab_c1:
        st.markdown("##### Postup u varného hrnce krok za krokem:")
        st.checkbox("1. Šrotování: Pluchy celé, zrno na krupici, minimální podíl mouky.")
        st.checkbox("2. Vystírka do vody 52–54 °C s upraveným pH (5.2–5.5).")
        st.checkbox("3. Dodrženy pauzy (bílkovinná, maltózová 63 °C, sacharizační 72 °C).")
        st.checkbox("4. Jodová zkouška je negativní (rmut je zcela zcukřen).")
        st.checkbox("5. Odrmutování (mash-out) na 78 °C a klid na lůžku 15 minut.")
        st.checkbox("6. Recirkulace sladiny do křišťálové čirosti a vyslazení vodou do 78 °C.")
        st.checkbox("7. Intenzivní chmelovar 90 min s otevřeným odparem a 3 dávkami chmele.")
        st.checkbox("8. Whirlpool a rychlé zchlazení mladiny pod 12 °C.")
        st.checkbox("9. Provzdušnění mladiny a zakvašení dostatečnou dávkou kvasinek.")

    with tab_c2:
        st.markdown("##### Záznamový list várky:")
        with st.form("form_zaznam_varky"):
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                v_nazev = st.text_input("Název piva", value="Světlý ležák 11°")
                v_datum = st.date_input("Datum vaření", value=datetime.today())
                v_slad = st.number_input("Sypání celkem (kg)", value=4.5, step=0.1)
            with c_l2:
                v_og = st.number_input("Naměřené OG (°Plato)", value=11.4, step=0.1)
                v_ph = st.number_input("Naměřené pH rmutu", value=5.35, step=0.05)
                v_obj = st.number_input("Objem mladiny v kvasné nádobě (l)", value=20.0, step=0.5)
            
            v_note = st.text_area("Poznámka sládka", "Krásný lom, čirá sladina, rychlý rozkvas.")
            if st.form_submit_button("💾 Uložit do protokolu"):
                entry = {"nazev": v_nazev, "datum": str(v_datum), "slad": v_slad, "og": v_og, "ph": v_ph, "objem": v_obj, "pozn": v_note}
                st.session_state.kurz.setdefault("batch_logs", []).append(entry)
                st.session_state.kurz["lessons"]["lekce9_10"]["completed"] = True
                save_data(st.session_state.kurz)
                st.success("✅ Várka byla úspěšně zaznamenána!")

    with tab_c3:
        splneno_celkem = sum(1 for l in st.session_state.kurz["lessons"].values() if l.get("completed", False))
        if splneno_celkem >= 7:
            st.balloons()
            st.markdown(f"""
            <div style="border: 4px solid #D97706; padding: 25px; border-radius: 12px; background-color: #FFFBEB; text-align: center; color: #1E293B;">
                <h1 style="color: #B45309; margin-bottom: 5px;">📜 CERTIFIKÁT DOMÁCÍHO SLÁDKA</h1>
                <p style="font-size: 1.1rem; margin-bottom: 15px;">Tímto se osvědčuje, že absolvent</p>
                <h2 style="color: #0F172A; text-decoration: underline; margin-bottom: 15px;">SLÁDEK MISTR</h2>
                <p style="font-size: 1rem; line-height: 1.6;">
                    úspěšně zvládl teorii i praxi výroby tradičního piva,<br>
                    výpočty chemie vody, rmutovací diagramy, kvašení i senzoriku.
                </p>
                <h4 style="color: #B45309; margin-top: 20px;">🍺 Dej Bůh štěstí! 🍺</h4>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning(f"Pro odemknutí certifikátu musíš mít splněno alespoň 7 lekcí kurzu (aktuálně: {splneno_celkem}/9).")

# =============================================================================
# DATABÁZE RECEPTŮ, EDITOR & GENERÁTOR S AUTO-IBU
# =============================================================================
elif selected_view == "📚 Databáze receptů":
    st.header("📚 Databáze receptů sládka")
    st.markdown("Ukládej, prohlížej, generuj a spravuj své pivní receptury.")
    st.divider()

    tab_new, tab_list, tab_gen = st.tabs(["➕ Nový recept", "📖 Moje recepty", "⚙️ Generátor receptů"])

    # --- TAB 1: VYTVOŘENÍ RECEPTU ---
    with tab_new:
        st.subheader("Vytvořit nový recept")

        r_c1, r_c2 = st.columns(2)
        with r_c1:
            r_name = st.text_input("Název receptu *", placeholder="např. Světlý ležák 11°")
            r_style = st.text_input("Styl piva", placeholder="Světlý ležák, APA, Stout...")
            r_batch = st.number_input("Objem várky (l)", value=20.0, step=1.0)
            r_og = st.number_input("Cílová stupňovitost (°P)", value=11.3, step=0.1)

        with r_c2:
            r_ibu = st.number_input("Cílová hořkost (IBU)", value=35.0, step=1.0)
            r_ebc = st.number_input("Barva piva (EBC / SRM)", value=9.0, step=0.5)
            r_yeast = st.text_input("Kvasnice", value="Saflager W-34/70")

        r_malts = st.text_area("Sypání (slady)", "Plzeňský slad: 4.2 kg\nMnichovský slad: 0.3 kg")

        # --- KALKULÁTOR CHMELENÍ ---
        CHMELY_DB = {
            "Žatecký poloraný červeňák (Saaz)": 3.8,
            "Sládek": 6.5,
            "Premiant": 8.5,
            "Kazbek": 6.0,
            "Agnus": 11.5,
            "Citra": 13.0,
            "Mosaic": 12.0,
            "Simcoe": 13.0,
            "Cascade": 6.5,
            "Amarillo": 9.0,
            "Magnum": 13.5,
            "Hallertau Mittelfrüh": 4.0
        }

        st.markdown("#### 🌿 Nastavení chmelového rozvrhu")

        col_h1, col_h2, col_h3 = st.columns([2, 1, 1])
        with col_h1:
            chmel_1 = st.selectbox("1. dávka (Hořkost):", list(CHMELY_DB.keys()), index=0, key="rec_chm1")
        with col_h2:
            alfa_1 = st.number_input("Alfa % (1)", value=CHMELY_DB[chmel_1], step=0.1, key="rec_alf1")
        with col_h3:
            cas_1 = st.number_input("Minut (1)", value=75, step=5, key="rec_cas1")

        col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
        with col_c1:
            chmel_2 = st.selectbox("2. dávka (Chuť):", list(CHMELY_DB.keys()), index=0, key="rec_chm2")
        with col_c2:
            alfa_2 = st.number_input("Alfa % (2)", value=CHMELY_DB[chmel_2], step=0.1, key="rec_alf2")
        with col_c3:
            cas_2 = st.number_input("Minut (2)", value=25, step=5, key="rec_cas2")

        col_a1, col_a2, col_a3 = st.columns([2, 1, 1])
        with col_a1:
            chmel_3 = st.selectbox("3. dávka (Aroma):", list(CHMELY_DB.keys()), index=0, key="rec_chm3")
        with col_a2:
            alfa_3 = st.number_input("Alfa % (3)", value=CHMELY_DB[chmel_3], step=0.1, key="rec_alf3")
        with col_a3:
            cas_3 = st.number_input("Minut (3)", value=5, step=5, key="rec_cas3")

        def get_utilization(time_min):
            if time_min >= 60: return 0.28
            if time_min >= 40: return 0.23
            if time_min >= 20: return 0.16
            if time_min >= 10: return 0.10
            return 0.05

        u1 = get_utilization(cas_1)
        u2 = get_utilization(cas_2)
        u3 = get_utilization(cas_3)

        varky_objem = float(r_batch)
        pozadovane_ibu = float(r_ibu)

        ibu_1 = pozadovane_ibu * 0.60
        ibu_2 = pozadovane_ibu * 0.30
        ibu_3 = pozadovane_ibu * 0.10

        g1 = round((ibu_1 * varky_objem) / (alfa_1 * u1 * 10), 1) if (alfa_1 * u1) > 0 else 0
        g2 = round((ibu_2 * varky_objem) / (alfa_2 * u2 * 10), 1) if (alfa_2 * u2) > 0 else 0
        g3 = round((ibu_3 * varky_objem) / (alfa_3 * u3 * 10), 1) if (alfa_3 * u3) > 0 else 0

        st.info(f"⚖️ **Doporučené dávky pro {pozadovane_ibu:.0f} IBU ({varky_objem:.0f} l):** 1. dávka: `{g1} g` ({ibu_1:.1f} IBU) | 2. dávka: `{g2} g` ({ibu_2:.1f} IBU) | 3. dávka: `{g3} g` ({ibu_3:.1f} IBU)")

        r_hops = f"{chmel_1} ({alfa_1}% alfa) {g1} g – {cas_1} min\n{chmel_2} ({alfa_2}% alfa) {g2} g – {cas_2} min\n{chmel_3} ({alfa_3}% alfa) {g3} g – {cas_3} min"

        r_notes = st.text_area("Poznámky k rmutování / várce", "Infuzní rmutování: 52 °C (15 min), 63 °C (40 min), 72 °C (20 min), mash-out 78 °C.")

        if st.button("💾 Uložit recept do databáze"):
            if not r_name.strip():
                st.error("Vyplň prosím název receptu.")
            else:
                new_entry = {
                    "name": r_name,
                    "style": r_style if r_style else "Neuvedeno",
                    "batch": r_batch,
                    "og": r_og,
                    "ibu": r_ibu,
                    "ebc": r_ebc,
                    "yeast": r_yeast,
                    "malts": r_malts,
                    "hops": r_hops,
                    "notes": r_notes,
                    "created_at": datetime.now().strftime("%d.%m.%Y")
                }
                st.session_state.kurz.setdefault("recipes", []).append(new_entry)
                save_data(st.session_state.kurz)
                st.success(f"Recept **{r_name}** byl úspěšně uložen!")
                st.rerun()

    # --- TAB 2: SEZNAM RECEPTŮ & EDITOR ---
    with tab_list:
        st.subheader("Moje uložené receptury")

        if st.session_state.edit_mode and st.session_state.edit_recipe_idx is not None:
            e_idx = st.session_state.edit_recipe_idx
            recipes_list = st.session_state.kurz.get("recipes", [])
            
            if 0 <= e_idx < len(recipes_list):
                r_edit = recipes_list[e_idx]
                st.info(f"✏️ **Režim úpravy receptu:** {r_edit.get('name', '')}")

                with st.form("form_edit_recipe"):
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        e_name = st.text_input("Název receptu", value=r_edit.get("name", ""))
                        e_style = st.text_input("Styl piva", value=r_edit.get("style", ""))
                        e_batch = st.number_input("Objem várky (l)", value=float(r_edit.get("batch", 20.0)), step=1.0)
                        e_og = st.number_input("OG (°P)", value=float(r_edit.get("og", 11.0)), step=0.1)

                    with ec2:
                        e_ibu = st.number_input("IBU", value=float(r_edit.get("ibu", 35.0)), step=1.0)
                        e_ebc = st.number_input("Barva (EBC / SRM)", value=float(r_edit.get("ebc", r_edit.get("srm", 8.0))), step=0.5)
                        e_yeast = st.text_input("Kvasnice", value=r_edit.get("yeast", ""))

                    e_malts = st.text_area("Sypání (slady)", value=r_edit.get("malts", ""))
                    e_hops = st.text_area("Chmelení (dávky)", value=r_edit.get("hops", ""))
                    e_notes = st.text_area("Poznámky sládka", value=r_edit.get("notes", ""))

                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        if st.form_submit_button("💾 Uložit změny"):
                            st.session_state.kurz["recipes"][e_idx] = {
                                "name": e_name,
                                "style": e_style,
                                "batch": e_batch,
                                "og": e_og,
                                "ibu": e_ibu,
                                "ebc": e_ebc,
                                "yeast": e_yeast,
                                "malts": e_malts,
                                "hops": e_hops,
                                "notes": e_notes,
                                "created_at": r_edit.get("created_at", datetime.now().strftime("%d.%m.%Y"))
                            }
                            save_data(st.session_state.kurz)
                            st.session_state.edit_mode = False
                            st.session_state.edit_recipe_idx = None
                            st.success("Recept byl úspěšně upraven!")
                            st.rerun()

                    with col_e2:
                        if st.form_submit_button("❌ Zrušit úpravy"):
                            st.session_state.edit_mode = False
                            st.session_state.edit_recipe_idx = None
                            st.rerun()

                st.divider()

        recipes = st.session_state.kurz.get("recipes", [])
        if not recipes:
            st.info("Zatím nemáš uložené žádné vlastní recepty. Vytvoř první v záložce 'Nový recept' nebo si vygeneruj z šablon.")
        else:
            for idx, r in enumerate(recipes):
                with st.expander(f"🍺 {r.get('name', 'Bez názvu')} — {r.get('style', 'Ležák')} ({r.get('created_at', '')})"):
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Objem", f"{r.get('batch', 20)} l")
                    m2.metric("Stupňovitost", f"{r.get('og', 11)} °P")
                    m3.metric("Hořkost", f"{r.get('ibu', 30)} IBU")
                    m4.metric("Barva", f"{r.get('ebc', r.get('srm', 10))} EBC")

                    st.markdown(f"**Kvasnice:** `{r.get('yeast', 'Nespecifikováno')}`")

                    c_m, c_h = st.columns(2)
                    with c_m:
                        st.markdown("**🌾 Sypání:**")
                        st.text(r.get("malts", ""))
                    with c_h:
                        st.markdown("**🌿 Chmelení:**")
                        st.text(r.get("hops", ""))

                    if r.get("notes"):
                        st.markdown("**📝 Poznámky:**")
                        st.caption(r["notes"])

                    st.divider()
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("🗑️ Smazat recept", key=f"del_rec_{idx}"):
                            st.session_state.kurz["recipes"].pop(idx)
                            st.session_state.edit_mode = False
                            st.session_state.edit_recipe_idx = None
                            save_data(st.session_state.kurz)
                            st.warning(f"Recept '{r.get('name', '')}' byl smazán.")
                            st.rerun()

                    with col_b2:
                        if st.button("✏️ Upravit recept", key=f"edit_rec_{idx}"):
                            st.session_state.edit_recipe_idx = idx
                            st.session_state.edit_mode = True
                            st.rerun()

    # --- TAB 3: GENERÁTOR RECEPTŮ S AUTO-IBU ---
    with tab_gen:
        st.subheader("⚙️ Automatický generátor receptů")
        st.markdown("Vyber styl piva, uprav si parametry chmelení a nechej IBU automaticky přepočítat.")

        style = st.selectbox("Vyber styl piva:", [
            "Světlý český ležák 11° (Jednormutová dekokce)",
            "Světlý český ležák 12° (Dvourmutová dekokce)",
            "Historický ležák 12° (Třírmutová dekokce)",
            "Polotmavý ležák 13° (Dvourmutová dekokce)",
            "Tmavý speciál 14° (Dvourmut)",
            "IPA 14° (Infuze)",
            "American Pale Ale 12° (Infuze)",
            "Německé pšeničné 12° (Ferulová infuze)"
        ])

        profiles = {
            "Světlý český ležák 11° (Jednormutová dekokce)": {
                "og": 11.3, "srm": 6, "batch": 20.0,
                "malts": "Plzeňský slad: 4.2 kg\nMnichovský slad: 0.3 kg\nCarapils: 0.1 kg",
                "hops_data": [
                    {"Nazev": "Premiant / Sládek (1. dávka)", "Hmotnost_g": 18.0, "Alfa_proc": 7.5, "Cas_min": 75},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 25},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Pivovarské husté kvasnice / W-34/70",
                "notes": "Jednormutová dekokce: Vystření na 52 °C (15 min). Ohřev na 63 °C. Odběr 1/3 hustého rmutu -> 72 °C (15 min) -> var rmutu 15 min. Vrácení a vyrovnání na 72 °C (cukření 20 min). Mash-out 78 °C. Kvašení při 7–9 °C."
            },
            "Světlý český ležák 12° (Dvourmutová dekokce)": {
                "og": 12.2, "srm": 8, "batch": 20.0,
                "malts": "Plzeňský slad: 4.8 kg\nMnichovský slad: 0.4 kg",
                "hops_data": [
                    {"Nazev": "ŽPČ (1. dávka)", "Hmotnost_g": 40.0, "Alfa_proc": 3.8, "Cas_min": 90},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 3.8, "Cas_min": 30},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Pivovarské husté kvasnice / Saflager W-34/70",
                "notes": "Klasická dvourmutová dekokce:\n1. Vystření na 37–52 °C (bílkovinná pauza 15 min).\n2. 1. rmut (1/3 hustého dílu): 63 °C (15 min), 72 °C (15 min), var 20 min -> vyrovnání celé varny na 63 °C (15 min).\n3. 2. rmut (1/3 hustého dílu): 72 °C (15 min), var 15 min -> vyrovnání celé varny na 72 °C (cukření 20 min).\n4. Mash-out na 78 °C. Chmelovar 90 min. Kvašení 7–8 °C, ležákování 1–3 °C 6 týdnů."
            },
            "Historický ležák 12° (Třírmutová dekokce)": {
                "og": 12.5, "srm": 10, "batch": 20.0,
                "malts": "Plzeňský slad (tradiční humnový): 5.2 kg",
                "hops_data": [
                    {"Nazev": "ŽPČ (1. dávka)", "Hmotnost_g": 45.0, "Alfa_proc": 3.8, "Cas_min": 90},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 35.0, "Alfa_proc": 3.8, "Cas_min": 30},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Spodní kvasinky (např. W-34/70 nebo tekuté)",
                "notes": "Historická třírmutová dekokce:\n1. Studené vystření na 35 °C.\n2. 1. rmut (1/3): 63 °C, 72 °C, var 25 min -> vyrovnání na 52 °C.\n3. 2. rmut (1/3): 63 °C, 72 °C, var 20 min -> vyrovnání na 63 °C.\n4. 3. rmut (1/3): 72 °C, var 15 min -> vyrovnání na 72 °C.\n5. Mash-out 78 °C. Hluboká zlatá barva a plná sladovost."
            },
            "Polotmavý ležák 13° (Dvourmutová dekokce)": {
                "og": 13.0, "srm": 14, "batch": 20.0,
                "malts": "Plzeňský slad: 4.2 kg\nMnichovský slad: 0.8 kg\nCaramunich II: 0.25 kg",
                "hops_data": [
                    {"Nazev": "Premiant (1. dávka)", "Hmotnost_g": 18.0, "Alfa_proc": 7.5, "Cas_min": 75},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 25},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 20.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Pivovarské husté kvasnice / W-34/70",
                "notes": "Dvourmutový postup. Karamelový slad (Caramunich) přidán až na druhý rmut pro zaoblenou karamelovou plnost bez trpkosti."
            },
            "Tmavý speciál 14° (Dvourmut)": {
                "og": 14.0, "srm": 35, "batch": 20.0,
                "malts": "Plzeňský slad: 4.0 kg\nMnichovský slad: 0.7 kg\nCarafa Special II: 0.25 kg\nCaramunich II: 0.3 kg",
                "hops_data": [
                    {"Nazev": "Premiant (1. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 7.5, "Cas_min": 60},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 10}
                ],
                "yeast": "Saflager W-34/70",
                "notes": "Dvourmutová dekokce světlých a mnichovských sladů. Barvicí slad Carafa Special přidán až na samotné scezování/vyslazování."
            },
            "IPA 14° (Infuze)": {
                "og": 14.0, "srm": 8, "batch": 20.0,
                "malts": "Pale Ale slad: 4.5 kg\nCarapils: 0.3 kg\nPšeničný slad: 0.3 kg",
                "hops_data": [
                    {"Nazev": "Citra (Hořkost)", "Hmotnost_g": 20.0, "Alfa_proc": 12.5, "Cas_min": 60},
                    {"Nazev": "Mosaic (Chuť)", "Hmotnost_g": 30.0, "Alfa_proc": 11.5, "Cas_min": 15},
                    {"Nazev": "Citra (Whirlpool 80°C)", "Hmotnost_g": 40.0, "Alfa_proc": 12.5, "Cas_min": 0}
                ],
                "yeast": "SafAle US-05",
                "notes": "Jednokroková infuze na 65 °C (60 min), mash-out 78 °C. Dry hopping: 50 g Citra + 50 g Mosaic na 3 dny před stáčením."
            },
            "American Pale Ale 12° (Infuze)": {
                "og": 12.0, "srm": 7, "batch": 20.0,
                "malts": "Pale Ale slad: 4.2 kg\nCarapils: 0.2 kg",
                "hops_data": [
                    {"Nazev": "Cascade (1. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 6.5, "Cas_min": 60},
                    {"Nazev": "Cascade (2. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 6.5, "Cas_min": 10},
                    {"Nazev": "Cascade (Whirlpool)", "Hmotnost_g": 40.0, "Alfa_proc": 6.5, "Cas_min": 0}
                ],
                "yeast": "SafAle US-05",
                "notes": "Infuze 66 °C (60 min), mash-out 78 °C. Jemná a vysoce pitelná APA."
            },
            "Německé pšeničné 12° (Ferulová infuze)": {
                "og": 12.0, "srm": 5, "batch": 20.0,
                "malts": "Pšeničný slad světlý: 2.6 kg\nPlzeňský slad: 2.2 kg",
                "hops_data": [
                    {"Nazev": "Hallertau Mittelfrüh (Hořkost)", "Hmotnost_g": 25.0, "Alfa_proc": 4.0, "Cas_min": 60}
                ],
                "yeast": "SafAle WB-06 / Munich Classic",
                "notes": "Infuze: Ferulová pauza 44 °C (15 min pro hřebíček) -> 63 °C (35 min) -> 72 °C (25 min) -> 78 °C mash-out. Kvašení při 20–22 °C pro banánové estery."
            }
        }

        p = profiles[style]

        st.markdown(f"### 📜 Profil stylu: **{style}**")
        col_gen1, col_gen2 = st.columns(2)
        with col_gen1:
            st.markdown(f"""
            * **Stupňovitost (OG):** `{p['og']} °P`
            * **Barva:** `{p['srm']} EBC`
            * **Objem várky:** `{p['batch']} l`
            * **Kvasnice:** `{p['yeast']}`
            """)
        with col_gen2:
            st.markdown(f"**🌾 Sypání:**\n```text\n{p['malts']}\n```")

        st.markdown("#### 🌿 Úprava chmelení a automatický přepočet IBU (Tinseth)")
        
        hop_df = pd.DataFrame(p["hops_data"])
        hop_edit = st.data_editor(
            hop_df,
            num_rows="dynamic",
            column_config={
                "Nazev": st.column_config.TextColumn("Dávka / Odrůda"),
                "Hmotnost_g": st.column_config.NumberColumn("Gramů (g)", min_value=0.0, step=5.0),
                "Alfa_proc": st.column_config.NumberColumn("Alfa (%)", min_value=0.1, max_value=25.0, step=0.1),
                "Cas_min": st.column_config.NumberColumn("Čas varu (min)", min_value=0, max_value=120, step=5),
            },
            use_container_width=True
        )

        calc_sg = 1.000 + (p["og"] * 4.0 / 1000.0)

        def tinseth_calc(row, vol, gravity):
            bigness = 1.65 * (0.000125 ** (gravity - 1.0))
            boil_factor = (1.0 - np.exp(-0.04 * row["Cas_min"])) / 4.15 if row["Cas_min"] > 0 else 0.05
            utilization = bigness * boil_factor
            mg_alpha = (row["Alfa_proc"] / 100.0) * row["Hmotnost_g"] * 1000.0
            return (mg_alpha * utilization) / vol

        ibu_total = 0.0
        hops_text_lines = []
        if not hop_edit.empty:
            for _, r in hop_edit.iterrows():
                ibu_total += tinseth_calc(r, p["batch"], calc_sg)
                hops_text_lines.append(f"{r['Nazev']} ({r['Alfa_proc']}% alfa) {r['Hmotnost_g']} g – {r['Cas_min']} min")

        st.metric("Vypočtená celková hořkost", f"{ibu_total:.1f} IBU")

        if st.button("💾 Uložit recept s vypočtenou IBU do mých receptů"):
            st.session_state.kurz.setdefault("recipes", []).append({
                "name": style,
                "style": style,
                "batch": p["batch"],
                "og": p["og"],
                "ibu": round(ibu_total, 1),
                "ebc": p["srm"],
                "malts": p["malts"],
                "hops": "\n".join(hops_text_lines),
                "yeast": p["yeast"],
                "notes": p["notes"],
                "created_at": datetime.now().strftime("%d.%m.%Y")
            })
            save_data(st.session_state.kurz)
            st.success(f"Recept '{style}' s IBU {ibu_total:.1f} byl úspěšně uložen do tvé databáze!")
            st.rerun()

# =============================================================================
# SLÁDKOVA POKROČILÁ KALKULAČKA
# =============================================================================
elif selected_view == "🧮 Sládkova pokročilá kalkulačka":
    st.header("🧮 Pokročilá kalkulačka sládka")
    st.markdown("Všechny pivovarské výpočty na jednom místě.")
    st.divider()

    t1, t2, t3 = st.tabs(["🌾 OG, Voda & Účinnost", "🌿 Hořkost IBU (Tinseth)", "🚰 Voda, RA & Kyselina mléčná"])

    # TAB 1: OG & VODA
    with t1:
        st.subheader("Výpočet objemu vody a původní stupňovitosti (OG)")
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            slad_kg = st.number_input("Hmotnost sypání sladu (kg)", value=4.5, step=0.1)
            cilovy_objem = st.number_input("Cílový objem mladiny do kvašení (l)", value=20.0, step=1.0)
            pomer_vody = st.slider(
                "Rmutovací poměr (l vody / 1 kg sladu)", 
                2.5, 4.5, 3.5, 0.1,
                help="Poměr udává, kolik litrů vody použijete na 1 kg sladu pro hlavní nálev (vystření).\n\n"
                     "• 2.5–3.0 l/kg: Hustý rmut (klasická dekokce, enzymy jsou chráněnější).\n"
                     "• 3.2–3.8 l/kg: Standard pro moderní infuzi a jednoplášťové varny (snadná cirkulace čerpadlem).\n"
                     "• 4.0+ l/kg: Velmi řídký rmut."
            )
            ucinnost_v = st.slider(
                "Účinnost varny (%)", 
                60, 85, 75, 1,
                help="Celková efektivita přechodu cukrů ze sladu do mladiny. U běžných domácích varen se pohybuje mezi 70–78 %."
            )

        with col_k2:
            odpar_h = st.number_input("Odpar při varu (l/hod)", value=3.0, step=0.5)
            cas_varu = st.number_input("Délka varu (min)", value=90, step=15)
            absorpce = 1.0

        rmut_voda = slad_kg * pomer_vody
        ztrata_slad = slad_kg * absorpce
        ztrata_odpar = odpar_h * (cas_varu / 60)
        celkova_voda = cilovy_objem + ztrata_slad + ztrata_odpar
        vyslaz_voda = celkova_voda - rmut_voda

        pts = (slad_kg * 308.0 * (ucinnost_v / 100.0)) / cilovy_objem
        sg_val = 1.000 + (pts / 1000.0)
        plato_val = pts / 4.0
        
        st.markdown("---")
        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        c_r1.metric("Hlavní nálev", f"{rmut_voda:.1f} l")
        c_r2.metric("Vyslazovací voda", f"{vyslaz_voda:.1f} l")
        c_r3.metric("Předpokládané OG", f"{plato_val:.1f} °P", f"{sg_val:.3f} SG")
        c_r4.metric("Celková voda", f"{celkova_voda:.1f} l")

    # TAB 2: IBU
    with t2:
        st.subheader("Výpočet hořkosti IBU (Tinsethova metoda)")
        c_ib1, c_ib2 = st.columns(2)
        with c_ib1:
            var_l = st.number_input("Objem při chmelovaru (l)", value=20.0, step=1.0)
            var_sg_in = st.number_input("Hustota mladiny při varu (SG)", value=1.045, step=0.002, format="%.3f")

        chmely_df = pd.DataFrame([
            {"Nazev": "1. ŽPČ (Hořkost)", "Hmotnost_g": 35.0, "Alfa_proc": 3.8, "Cas_min": 75},
            {"Nazev": "2. ŽPČ (Chuť)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 25},
            {"Nazev": "3. ŽPČ (Aroma)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 5},
        ])
        ed_df = st.data_editor(chmely_df, num_rows="dynamic", use_container_width=True)

        def calc_single_ibu(row, vol, gravity):
            bigness = 1.65 * (0.000125 ** (gravity - 1.0))
            boil_f = (1.0 - np.exp(-0.04 * row["Cas_min"])) / 4.15
            util = bigness * boil_f
            mg_a = (row["Alfa_proc"] / 100.0) * row["Hmotnost_g"] * 1000.0
            return (mg_a * util) / vol

        if not ed_df.empty:
            ed_df["IBU"] = ed_df.apply(lambda r: calc_single_ibu(r, var_l, var_sg_in), axis=1)
            tot_ibu = ed_df["IBU"].sum()
            st.metric("Celková vypočtená hořkost", f"{tot_ibu:.1f} IBU")

    # TAB 3: VODA, RA & KYSELINA
    with t3:
        st.subheader("Minerální profil, zbytková alkalita a dávkování kyseliny mléčné")
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            w_vol = st.number_input("Objem rmutovací vody (l)", value=15.0, step=1.0)
            w_slad = st.number_input("Slad do rmutu (kg)", value=4.5, step=0.1)
            st.markdown("**Zdrojová voda (ppm / mg/l):**")
            w_ca = st.number_input("Vápník (Ca²⁺)", value=25.0)
            w_mg = st.number_input("Hořčík (Mg²⁺)", value=6.0)
            w_so4 = st.number_input("Sírany (SO₄²⁻)", value=20.0)
            w_cl = st.number_input("Chloridy (Cl⁻)", value=15.0)
            w_hco3 = st.number_input("Hydrogenuhličitany (HCO₃⁻)", value=65.0)

        with col_w2:
            st.markdown("**Přídavky pivovarských solí do rmutu (g):**")
            g_cacl2 = st.number_input("Chlorid vápenatý (CaCl₂ · 2H₂O) [g]", value=2.0, step=0.5)
            g_gypsum = st.number_input("Sádrovec (CaSO₄ · 2H₂O) [g]", value=0.0, step=0.5)
            target_ph = st.slider("Cílové pH rmutu", 5.20, 5.60, 5.35, 0.05)

        ca_add = ((g_gypsum * 232.8) + (g_cacl2 * 272.6)) / w_vol
        so4_add = (g_gypsum * 557.9) / w_vol
        cl_add = (g_cacl2 * 482.3) / w_vol
        f_ca, f_mg, f_so4, f_cl, f_hco3 = w_ca + ca_add, w_mg, w_so4 + so4_add, w_cl + cl_add, w_hco3

        alk_caco3 = f_hco3 * (50.04 / 61.02)
        ra_ppm = alk_caco3 - ((f_ca / 1.4) + (f_mg / 1.7))
        ra_dh = ra_ppm / 17.848
        est_ph = 5.75 + (0.03 * ra_dh)

        d_ph = est_ph - target_ph
        ml_kyseliny = max(0.0, (d_ph * (45.0 * w_slad)) / 11.6) if d_ph > 0 else 0.0

        st.divider()
        r_w1, r_w2, r_w3, r_w4 = st.columns(4)
        r_w1.metric("Zbytková alkalita (RA)", f"{ra_dh:.1f} °dH")
        r_w2.metric("Odhad pH bez úpravy", f"{est_ph:.2f}")
        r_w3.metric("Cílové pH", f"{target_ph:.2f}")
        r_w4.metric("Dávka 80% kys. mléčné", f"{ml_kyseliny:.1f} ml")

        st.info(f"💡 **Instrukce pro vystírku:** Přidej **{ml_kyseliny:.1f} ml** 80% kyseliny mléčné do {w_vol:.1f} l vystírací vody před nasypáním sladu.")

# =============================================================================
# ČASOVAČ VARNÉHO DNE
# =============================================================================
elif selected_view == "⏱️ Časovač varného dne":
    st.header("⏱️ Asistent varného dne (Live Timer)")
    st.markdown("Časovač fází rmutování a chmelovaru se zvukovou a vizuální notifikací.")
    st.divider()

    t_mod = st.radio("Režim časovače:", ["🔥 Rmutovací křivka", "🌿 Chmelovar"], horizontal=True)

    if t_mod == "🔥 Rmutovací křivka":
        c1, c2, c3 = st.columns(3)
        with c1: p_b = st.number_input("Bílkovinná pauza 52 °C (min)", 0, 60, 15, 5)
        with c2: p_m = st.number_input("Maltózová pauza 63 °C (min)", 10, 90, 40, 5)
        with c3: p_s = st.number_input("Sacharizační pauza 72 °C (min)", 10, 60, 20, 5)
        
        phases = []
        if p_b > 0: phases.append({"nazev": "Bílkovinná pauza (52 °C)", "cas": p_b})
        phases.append({"nazev": "Maltózová pauza (63 °C)", "cas": p_m})
        phases.append({"nazev": "Sacharizační pauza (72 °C)", "cas": p_s})
        phases.append({"nazev": "Mash-out (78 °C)", "cas": 5})
    else:
        phases = [
            {"nazev": "Náběh varu & lom", "cas": 15},
            {"nazev": "1. Chmelení (Hořkost)", "cas": 50},
            {"nazev": "2. Chmelení (Chuť)", "cas": 20},
            {"nazev": "3. Chmelení & Whirlpool", "cas": 5}
        ]

    total_sec = sum(p["cas"] for p in phases) * 60
    cum_limits = []
    curr_s = 0
    for p in phases:
        curr_s += p["cas"] * 60
        cum_limits.append(curr_s)

    @st.fragment(run_every="1s")
    def render_timer_ui(phases_list, total_duration, limits):
        b1, b2 = st.columns(2)
        with b1:
            if not st.session_state.timer_running:
                if st.button("▶️ Spustit časovač", use_container_width=True):
                    st.session_state.timer_running = True
                    st.session_state.timer_start_time = time.time()
                    st.rerun(scope="fragment")
            else:
                if st.button("⏸️ Pozastavit časovač", use_container_width=True):
                    st.session_state.timer_running = False
                    st.session_state.timer_elapsed_offset += time.time() - st.session_state.timer_start_time
                    st.rerun(scope="fragment")
        with b2:
            if st.button("🔄 Resetovat", use_container_width=True):
                st.session_state.timer_running = False
                st.session_state.timer_start_time = 0.0
                st.session_state.timer_elapsed_offset = 0.0
                st.session_state.last_alert_phase = -1
                st.rerun(scope="fragment")

        if st.session_state.timer_running:
            el = st.session_state.timer_elapsed_offset + (time.time() - st.session_state.timer_start_time)
        else:
            el = st.session_state.timer_elapsed_offset

        el = min(el, total_duration)
        rem = max(0, total_duration - el)

        curr_p_idx = 0
        for idx, limit in enumerate(limits):
            if el < limit:
                curr_p_idx = idx
                break
            else:
                curr_p_idx = len(phases_list) - 1

        if st.session_state.timer_running and curr_p_idx != st.session_state.last_alert_phase:
            play_sound_alert()
            st.toast(f"🔔 Přechod na fázi: {phases_list[curr_p_idx]['nazev']}!", icon="🍺")
            st.session_state.last_alert_phase = curr_p_idx

        m_el, s_el = divmod(int(el), 60)
        m_rem, s_rem = divmod(int(rem), 60)

        disp1, disp2, disp3 = st.columns(3)
        disp1.metric("Uplynulo", f"{m_el:02d}:{s_el:02d}")
        disp2.metric("Zbývá", f"{m_rem:02d}:{s_rem:02d}")
        p_ratio = el / total_duration if total_duration > 0 else 0
        disp3.metric("Postup", f"{int(p_ratio * 100)} %")
        st.progress(p_ratio)

        if rem > 0:
            st.success(f"📍 Aktuálně probíhá: **{phases_list[curr_p_idx]['nazev']}** ({phases_list[curr_p_idx]['cas']} min)")
        else:
            st.balloons()
            st.success("🎉 Fáze dokončena!")

    render_timer_ui(phases, total_sec, cum_limits)
