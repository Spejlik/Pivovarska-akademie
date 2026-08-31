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
FIREBASE_WEB_API_KEY = "AIzaSyDi045x3p6Z8YmlF9Hms515WvoIkXqCfSU"  # <-- Zkopíruj z Firebase Project Settings

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
        "lekce8": {"title": "8. Receptury & Tvorba ležáku", "completed": False, "score": 0},
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

menu_items = [
    "📘 1. Základy & Suroviny",
    "🚰 2. Voda a její úprava",
    "🔥 3. Rmutování & Enzymy",
    "🪣 4. Scezování & Recirkulace",
    "🧪 5. Kvašení & Diacetyl",
    "❄️ 6. Ležákování & KEG CO₂",
    "👃 7. Senzorika & Pivní vady",
    "🌾 8. Receptury & Tvorba ležáku",
    "📋 9 & 10. Checklist & Várka",
    "---",
    "📚 Databáze receptů",
    "🧮 Sládkova pokročilá kalkulačka",
    "⏱️ Časovač varného dne"
]

selected_view = st.sidebar.radio("Přejít na:", menu_items)

# =============================================================================
# LEKCE 1: ZÁKLADY & SUROVINY
# =============================================================================
if selected_view == "📘 1. Základy & Suroviny":
    st.header("Lekce 1: Základy a suroviny")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        ### 4 pilíře piva:
        1. **Voda:** Tvoří přes 90 % piva. Ionty ($Ca^{2+}, Mg^{2+}, Cl^-, SO_4^{2-}$) definují charakter sladovosti a ostrosti hořkosti.
        2. **Slad:** Naklíčený a šetrně usušený ječmen. Zdroj enzymů a zkvasitelného extraktu.
        3. **Chmel:** Dodává hořkost (alfa-kyseliny) a aroma (chmelové silice). Působí antibakteriálně.
        4. **Kvasnice:**
           * *Spodní (Saccharomyces pastorianus):* Ležáky ($8–12\,^\circ\text{C}$).
           * *Svrchní (Saccharomyces cerevisiae):* Ale, Stout, Pšenice ($16–22\,^\circ\text{C}$).
        """)
    with col2:
        st.info("💡 **Základní pravidlo:** Ležák neodpouští chyby – nízká teplota kvašení zaručuje čistý profil bez nežádoucích ovocných esterů.")

    st.subheader("Mini-kvíz: Prověř si znalosti")
    with st.form("form_lekce1"):
        q1 = st.radio("Při jaké teplotě probíhá hlavní kvašení spodně kvašeného českého ležáku?", ["18–22 °C", "8–12 °C", "0–2 °C"])
        q2 = st.radio("Která složka chmele poskytuje trvalou hořkost po dlouhém varu?", ["Silice a aroma oleje", "Izomerizované alfa-kyseliny", "Třísloviny z listů"])
        if st.form_submit_button("Vyhodnotit kvíz"):
            if q1 == "8–12 °C" and q2 == "Izomerizované alfa-kyseliny":
                st.success("🎉 Skvěle! Obě odpovědi jsou správné.")
                st.session_state.kurz["lessons"]["lekce1"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Něco není správně, zkus to znovu.")

    render_mentor(
        "Kupuj plzeňský slad z prověřených humnových nebo moderních sladoven. Vždy zkontroluj, zda není navlhlý.",
        "Skladování chmele v teple a na vzduchu vede k oxidaci alfa-kyselin (sýrový pach). Chmel patří vždy do mrazáku a vakuového obalu!"
    )

# =============================================================================
# LEKCE 2: VODA A JEJÍ ÚPRAVA
# =============================================================================
elif selected_view == "🚰 2. Voda a její úprava":
    st.header("Lekce 2: Voda a její chemická úprava")
    st.markdown("""
    Tradiční plzeňský ležák vznikl na **extrémně měkké vodě** s minimem minerálů.
    * **Vápník ($Ca^{2+}$):** Klíčový pro enzymatickou aktivitu a srážení bílkovin (cíl: 30–50 ppm).
    * **Poměr Síranů a Chloridů ($SO_4^{2-} / Cl^-$):**
      * $Cl^-$ zvýrazňuje sladovost a plnost těla.
      * $SO_4^{2-}$ dává suchou a říznou hořkost.
      * Pro český ležák cílíme na vyrovnaný poměr cca **1:1 až 1:1.2** ve prospěch chloridů.
    * **pH rmutu:** Cílové rozmezí při $20\,^\circ\text{C}$ je **5.2 – 5.5**. Vyšší pH louhuje z pluch drsné třísloviny.
    """)

    with st.form("form_lekce2"):
        q = st.radio("Jaké je optimální pH rmutu pro správnou enzymatickou přeměnu škrobů?", ["6.2 – 6.8", "5.2 – 5.5", "4.0 – 4.5"])
        if st.form_submit_button("Odevzdat odpověď"):
            if q == "5.2 – 5.5":
                st.success("Správně! V tomto rozmezí optimálně fungují beta i alfa amylázy.")
                st.session_state.kurz["lessons"]["lekce2"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Nesprávně. Příliš vysoké pH snižuje výtěžnost a zvyšuje trpkost.")

    render_mentor(
        "Pro úpravu pH používej 80% potravinářskou kyselinu mléčnou. Dávkuj ji přímo do vystírací vody ještě před nasypáním sladu.",
        "Měření pH dělej vždy po ochlazení vzorku na pokojovou teplotu (20 °C). Horký rmut ukáže pH o 0.3 nižší a zničí sondu!"
    )

# =============================================================================
# LEKCE 3: RMUTOVÁNÍ & ENZYMY
# =============================================================================
elif selected_view == "🔥 3. Rmutování & Enzymy":
    st.header("Lekce 3: Rmutování, enzymatika a rmutovací křivky")
    st.markdown("""
    Rmutování je proces aktivace enzymů obsažených ve sladu pro rozštěpení škrobů na zkvasitelné a nezkvasitelné cukry:
    * **Bílkovinná pauza ($50–54\,^\circ\text{C}$):** Štěpení bílkovin na aminokyseliny a střední bílkoviny pro pěnu.
    * **Maltózová pauza ($62–65\,^\circ\text{C}$):** Beta-amyláza tvoří zkvasitelnou maltózu $\\rightarrow$ *sušší pivo*.
    * **Sacharizační pauza ($70–74\,^\circ\text{C}$):** Alfa-amyláza tvoří nezkvasitelné dextriny $\\rightarrow$ *plné tělo*.
    * **Mash-out ($76–78\,^\circ\text{C}$):** Deaktivace enzymů a snížení viskozity pro snadné scezování.
    """)

    cas = [0, 15, 25, 65, 75, 95, 100, 105]
    teploty = [52, 52, 63, 63, 72, 72, 78, 78]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(cas, teploty, marker='o', color='#D97706', linewidth=2.5)
    ax.set_title("Infuzní diagram ležáku 11°")
    ax.set_xlabel("Čas (minuty)")
    ax.set_ylabel("Teplota (°C)")
    ax.grid(True, linestyle="--", alpha=0.4)
    st.pyplot(fig)
    plt.close(fig)

    with st.form("form_lekce3"):
        q = st.radio("Který enzym vytváří nezkvasitelné dextriny pro plné tělo ležáku?", ["Beta-amyláza (62–65 °C)", "Alfa-amyláza (70–74 °C)", "Peptidáza (50 °C)"])
        if st.form_submit_button("Zkontrolovat"):
            if q == "Alfa-amyláza (70–74 °C)":
                st.success("Výborně! Alfa-amyláza štěpí škrob náhodně a vytváří komplexnější cukry.")
                st.session_state.kurz["lessons"]["lekce3"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Chyba. Beta-amyláza tvoří jednoduchou zkvasitelnou maltózu.")

    render_mentor(
        "Před odrmutováním udělej vždy jodovou zkoušku (kapka rmutu na bílý talířek + kapka jodu). Pokud nezmodrá, rmut je plně zcukřen!",
        "Nikdy nepřekračuj teplotu 78 °C. Nad 80 °C začnou pluchy uvolňovat svíravé taniny."
    )

# =============================================================================
# LEKCE 4: SCEZOVÁNÍ & RECIRKULACE
# =============================================================================
elif selected_view == "🪣 4. Scezování & Recirkulace":
    st.header("Lekce 4: Scezování, tvorba filtračního koláče a recirkulace")
    st.markdown("""
    Při scezování nefiltruje samotné nerezové síto, ale **filtrační lůžko ze sladových pluch**.
    * **Klid na lůžku (10–15 min):** Po odrmutování nech rmut usadit.
    * **Recirkulace (Vorlauf):** První vytékající zakalenou sladinu jemně vracíme zpět na hladinu, dokud neteče křišťálově čirá.
    * **Vyslazovací voda ($76–78\,^\circ\text{C}$):** Nesmí přesáhnout $80\,^\circ\text{C}$.
    """)

    if "recirc_sim" not in st.session_state:
        st.session_state.recirc_sim = 0.0

    c_s1, c_s2 = st.columns([1, 1])
    with c_s1:
        if st.button("🪣 Vrátit 1 litr sladiny na hladinu"):
            st.session_state.recirc_sim += 1.0
        if st.button("🔄 Resetovat simulaci"):
            st.session_state.recirc_sim = 0.0

    with c_s2:
        val = st.session_state.recirc_sim
        st.write(f"Recirkulováno: **{val:.1f} litrů**")
        if val == 0:
            st.error("Stav: Silně zakalená (moučný kal) 🟤")
        elif val < 2.0:
            st.warning("Stav: Mírný zákal 🟠")
        else:
            st.success("Stav: Křišťálově čirá sladina ✨🟢 (Lůžko je usazeno)")

    with st.form("form_lekce4"):
        q = st.radio("Co uděláš, když se scezování zcela zastaví (stuck sparge)?", [
            "Otevřu kohout naplno",
            "Zavřu kohout, uvolním podtlak a opatrně nařežu horní vrstvu mláta",
            "Naleji dovnitř vařící vodu o 100 °C"
        ])
        if st.form_submit_button("Odevzdat test"):
            if "uvolním podtlak" in q:
                st.success("Správně! Podtlak zhutnil pluchy a je nutné je opatrně proříznout.")
                st.session_state.kurz["lessons"]["lekce4"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Špatně. Rychlé otevření situaci ještě zhorší.")

    render_mentor(
        "Při vracení sladiny na hladinu použij děrovanou lžíci, ať proud tekutiny nerozrazí filtrační koláč.",
        "Nikdy nevyslazuj vodou teplejší než 80 °C. Uvolněné třísloviny způsobí trpkou pachuť."
    )

# =============================================================================
# LEKCE 5: KVAŠENÍ & DIACETYL
# =============================================================================
elif selected_view == "🧪 5. Kvašení & Diacetyl":
    st.header("Lekce 5: Spodní kvašení, Pitching rate a Diacetyl rest")
    st.markdown("""
    Spodní kvasinky (*S. pastorianus*) pracují při $8–12\,^\circ\text{C}$ a vyžadují **dvojnásobnou dávku (1.5 mil. buněk/ml/°P)** oproti svrchnímu kvašení.
    * **Diacetyl (máslová chuť):** Přirozený vedlejší produkt.
    * **Diacetyl rest:** Zvýšení teploty z $9\,^\circ\text{C}$ na **$13–15\,^\circ\text{C}$** ve chvíli, kdy zbývá prokvasit posledních 20–25 % cukrů. Kvasinky díky vyšší teplotě rychle diacetyl zkonzumují.
    """)

    with st.form("form_lekce5"):
        q1 = st.radio("Kolik balíčků suchých kvasinek (11.5g) je potřeba pro 20 litrů 12° ležáku?", ["Pouze 1/2 balíčku", "1 balíček", "Minimálně 2 balíčky (pro ležácký pitching rate)"])
        q2 = st.radio("Kdy zahajujeme Diacetyl rest?", ["Až po 4 týdnech v KEGu", "Ke konci hlavního kvašení při dokvašování posledních 20–25 % cukrů", "Při vystírání sladu"])
        if st.form_submit_button("Vyhodnotit lekci 5"):
            if "Minimálně 2" in q1 and "Ke konci hlavního" in q2:
                st.success("Skvěle! Správná dávka kvasinek a včasný diacetyl rest jsou tajemstvím čistého ležáku.")
                st.session_state.kurz["lessons"]["lekce5"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.warning("Zkontroluj si doporučené dávkování a teplotní okna.")

    render_mentor(
        "Před zachlazením do ležáckého tanku otestuj diacetyl v mikrovlnce: ohřej vzorek na 60 °C na 20 s, zakryj a přičichni. Pokud necítíš teplé máslo, můžeš chladit.",
        "Předčasné zchlazení uspí kvasinky a diacetyl už v pivu zůstane navždy."
    )

# =============================================================================
# LEKCE 6: LEŽÁKOVÁNÍ & KEG CO2
# =============================================================================
elif selected_view == "❄️ 6. Ležákování & KEG CO₂":
    st.header("Lekce 6: Ležákování v chladu a nasycení v KEGu")
    st.markdown("""
    * **Teplota ležákování ($1–3\,^\circ\text{C}$):** Usnadňuje vysrážení chladového zákalu (*chill haze*) a sedimentaci zbytkových kvasinek.
    * **Délka zrání:** Pravidlo sládků: **1 týden na každý 1 stupeň Plato** (11° ležák = 4–5 týdnů).
    * **Henryho zákon sycení:** V chladnějším pivu se $CO_2$ rozpouští výrazně ochotněji.
    """)

    with st.form("form_lekce6"):
        q = st.radio("Proč před plněním Corny KEGu vytěsňujeme vzduch plynem CO₂?", [
            "Abychom sud ochladili",
            "Abychom zabránili oxidaci piva (chuti po mokrém kartonu)",
            "Aby se zvýšila pěnivost mladiny"
        ])
        if st.form_submit_button("Odevzdat test"):
            if "oxidaci" in q:
                st.success("Přesně tak! Kyslík je po ukončení kvašení největším nepřítelem piva.")
                st.session_state.kurz["lessons"]["lekce6"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Chyba. Hlavním důvodem je ochrana před vzdušným kyslíkem.")

    render_mentor(
        "Při narážení a čepování udržuj stejnou teplotu sudu i vedení. Zabráníš tím uvolňování bublinek CO₂ v hadici a pěnění na pípě.",
        "Nikdy nasyť pivo divokým třesením pod 3 bary bez kontroly, jinak budeš točit jen pěnu."
    )

# =============================================================================
# LEKCE 7: SENZORIKA & PIVNÍ VADY
# =============================================================================
elif selected_view == "👃 7. Senzorika & Pivní vady":
    st.header("Lekce 7: Senzorika piva & Rozpoznávání pivních vad (Off-flavors)")
    st.markdown("*Identifikace nejčastějších technologických vad a jejich původ.*")
    
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.markdown("""
        * **🧈 Diacetyl:** Chuť másla, popcornu. *Původ: Nízký pitching rate, předčasné zachlazení.*
        * **🌽 DMS:** Vařená kukuřice, sterilovaný hrášek. *Původ: Slabý var se zakrytou poklicí, pomalé chlazení.*
        """)
    with col_v2:
        st.markdown("""
        * **📦 Oxidace:** Mokrý karton, zatuchlý sklep, těžký med. *Původ: Kontakt se vzduchem při stáčení.*
        * **🍏 Acetaldehyd:** Zelené nakyslé jablko, tráva. *Původ: Nedokvašené mladé pivo.*
        """)

    with st.form("form_lekce7"):
        q = st.radio("Co je hlavní příčinou vzniku DMS (kukuřičné příchuti) v ležáku?", [
            "Slabý chmelovar se zakrytou poklicí bez možnosti odparu a pomalé chlazení",
            "Kvašení při příliš nízké teplotě",
            "Příliš mnoho žateckého chmele"
        ])
        if st.form_submit_button("Vyhodnotit test"):
            if "Slabý chmelovar" in q:
                st.success("Správně! Prekurzor DMS se musí intenzivním varem odpařit.")
                st.session_state.kurz["lessons"]["lekce7"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Chyba. DMS vzniká tepelným rozkladem SMM bez dostatečného odparu páry.")

    render_mentor(
        "Referenční vzorky si vyrobíš doma: kapka máslového aroma do piva = diacetyl, kapka nálevu z kukuřice = DMS.",
        "Pivo na senzoriku degustuj při 8–10 °C. Příliš ledové pivo vady spolehlivě zamaskuje!"
    )

# =============================================================================
# LEKCE 8: RECEPTURY & TVORBA LEŽÁKU
# =============================================================================
elif selected_view == "🌾 8. Receptury & Tvorba ležáku":
    st.header("Lekce 8: Receptury a tvorba tradičního ležáku")
    st.markdown("""
    * **Základ sypání (95–100 %):** Český plzeňský slad.
    * **Doplňkové slady (0–5 %):** Mnichovský slad (pro chlebovost a barvu) nebo Carapils (pěna).
    * **Chmelový rozvrh (3 dávky ŽPČ):**
      * 1. dávka (75–90 min) = 65 % IBU (hořkost)
      * 2. dávka (25 min) = 25 % IBU (chuť)
      * 3. dávka (5 min / whirlpool) = 10 % IBU (aroma)
    """)

    with st.form("form_lekce8"):
        q = st.radio("Jaký poměr BU:GU (hořkost ku hustotě) je typický pro dobře vyvážený český ležák?", [
            "0.10 až 0.20 (téměř bez hořkosti)",
            "0.70 až 0.85 (střední až vyšší harmonická hořkost)",
            "1.50 až 2.00 (extrémní IPA)"
        ])
        if st.form_submit_button("Odevzdat"):
            if "0.70 až 0.85" in q:
                st.success("Správně! Český ležák vyžaduje poctivou pevnou hořkost vyvažující sladové tělo.")
                st.session_state.kurz["lessons"]["lekce8"]["completed"] = True
                save_data(st.session_state.kurz)
            else:
                st.error("Nesprávně. Správné rozmezí pro český styl je 0.70–0.85.")

    render_mentor(
        "Nepřeplňuj recept speciálními slady. Tradiční ležák staví na kráse jednoduchosti a kvalitě plzeňského sladu.",
        "Při použití výhradně žateckého červeňáku počítej s velkým množstvím chmelového kalu. Dobrý whirlpool je zásadní."
    )

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
                    úspěšně zvládl teorii i praxi výroby tradičního českého ležáku,<br>
                    výpočty chemie vody, rmutovací diagramy, kvašení i senzoriku piva.
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

        with st.form("form_new_recipe"):
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
            r_hops = st.text_area("Chmelový rozvrh", "ŽPČ (3.8% alfa) 35 g – 75 min\nŽPČ (3.8% alfa) 25 g – 25 min\nŽPČ (3.8% alfa) 25 g – 5 min")
            r_notes = st.text_area("Poznámky k rmutování / várce", "Infuzní rmutování: 52 °C (15 min), 63 °C (40 min), 72 °C (20 min), mash-out 78 °C.")

            submit_recipe = st.form_submit_button("💾 Uložit recept do databáze")

            if submit_recipe:
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

        # FORMULÁŘ EDITACE
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

        # VÝPIS ULOŽENÝCH RECEPTŮ
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
            "Světlý český ležák 11°",
            "Světlý český ležák 12°",
            "Polotmavý ležák 13°",
            "Tmavý speciál 14°",
            "IPA 14°",
            "American Pale Ale 12°"
        ])

        profiles = {
            "Světlý český ležák 11°": {
                "og": 11.0, "srm": 6, "batch": 20.0,
                "malts": "Plzeňský slad: 4.5 kg\nCarapils: 0.2 kg",
                "hops_data": [
                    {"Nazev": "ŽPČ (1. dávka)", "Hmotnost_g": 35.0, "Alfa_proc": 3.8, "Cas_min": 75},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 25},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Saflager W-34/70 (2 balíčky)",
                "notes": "Klasický český ležák s pevnou hořkostí a čistým profilem."
            },
            "Světlý český ležák 12°": {
                "og": 12.0, "srm": 7, "batch": 20.0,
                "malts": "Plzeňský slad: 5.0 kg\nCarapils: 0.3 kg",
                "hops_data": [
                    {"Nazev": "ŽPČ (1. dávka)", "Hmotnost_g": 40.0, "Alfa_proc": 3.8, "Cas_min": 75},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 3.8, "Cas_min": 25},
                    {"Nazev": "ŽPČ (3. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 3.8, "Cas_min": 5}
                ],
                "yeast": "Saflager W-34/70 (2 balíčky)",
                "notes": "Plnější tělo, vyšší hořkost, ideální pro klasickou prémiovou dvanáctku."
            },
            "Polotmavý ležák 13°": {
                "og": 13.0, "srm": 14, "batch": 20.0,
                "malts": "Plzeňský slad: 4.5 kg\nMnichovský slad: 0.5 kg\nCaramunich I: 0.2 kg",
                "hops_data": [
                    {"Nazev": "ŽPČ (1. dávka)", "Hmotnost_g": 35.0, "Alfa_proc": 3.8, "Cas_min": 60},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 20}
                ],
                "yeast": "Saflager W-34/70 (2 balíčky)",
                "notes": "Chlebové tóny, jemná karamelovost a vyvážená hořkost."
            },
            "Tmavý speciál 14°": {
                "og": 14.0, "srm": 35, "batch": 20.0,
                "malts": "Plzeňský slad: 4.0 kg\nMnichovský slad: 0.5 kg\nCarafa II: 0.2 kg\nCaramunich II: 0.3 kg",
                "hops_data": [
                    {"Nazev": "Premiant (1. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 7.5, "Cas_min": 60},
                    {"Nazev": "ŽPČ (2. dávka)", "Hmotnost_g": 25.0, "Alfa_proc": 3.8, "Cas_min": 10}
                ],
                "yeast": "Saflager W-34/70 (2 balíčky)",
                "notes": "Tmavé tóny pražené čokolády, karamelu a jemná hořkost."
            },
            "IPA 14°": {
                "og": 14.0, "srm": 8, "batch": 20.0,
                "malts": "Pale Ale slad: 4.5 kg\nCarapils: 0.3 kg",
                "hops_data": [
                    {"Nazev": "Citra (Hořkost)", "Hmotnost_g": 25.0, "Alfa_proc": 12.5, "Cas_min": 60},
                    {"Nazev": "Mosaic (Chuť)", "Hmotnost_g": 30.0, "Alfa_proc": 11.5, "Cas_min": 15},
                    {"Nazev": "Citra (Whirlpool)", "Hmotnost_g": 40.0, "Alfa_proc": 12.5, "Cas_min": 0}
                ],
                "yeast": "SafAle US-05 (1 balíček)",
                "notes": "Citrusová a tropická IPA s výraznou, pevnou hořkostí. Možno přidat 50g Mosaic na Dry Hop."
            },
            "American Pale Ale 12°": {
                "og": 12.0, "srm": 7, "batch": 20.0,
                "malts": "Pale Ale slad: 4.2 kg\nCarapils: 0.2 kg",
                "hops_data": [
                    {"Nazev": "Cascade (1. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 6.5, "Cas_min": 60},
                    {"Nazev": "Cascade (2. dávka)", "Hmotnost_g": 30.0, "Alfa_proc": 6.5, "Cas_min": 10},
                    {"Nazev": "Cascade (Whirlpool)", "Hmotnost_g": 40.0, "Alfa_proc": 6.5, "Cas_min": 0}
                ],
                "yeast": "SafAle US-05 (1 balíček)",
                "notes": "Lehká, vysoce pitelná citrusová APA s jemnou květinovou hořkostí."
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

        # Úprava chmelení a výpočet IBU
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
            pomer_vody = st.slider("Rmutovací poměr (l vody / 1 kg sladu)", 2.5, 4.5, 3.5, 0.1)
            ucinnost_v = st.slider("Účinnost varny (%)", 60, 85, 75, 1)
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
            var_l = st.number_input("Objem při chmelovaru (l)", value=cilovy_objem, step=1.0)
            var_sg_in = st.number_input("Hustota mladiny při varu (SG)", value=float(f"{sg_val:.3f}"), step=0.002, format="%.3f")

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
            w_vol = st.number_input("Objem rmutovací vody (l)", value=rmut_voda, step=1.0)
            w_slad = st.number_input("Slad do rmutu (kg)", value=slad_kg, step=0.1)
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

        # Ionty
        ca_add = ((g_gypsum * 232.8) + (g_cacl2 * 272.6)) / w_vol
        so4_add = (g_gypsum * 557.9) / w_vol
        cl_add = (g_cacl2 * 482.3) / w_vol
        f_ca, f_mg, f_so4, f_cl, f_hco3 = w_ca + ca_add, w_mg, w_so4 + so4_add, w_cl + cl_add, w_hco3

        # Kolbachova Zbytková Alkalita
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
# ČASOVAČ VARNÉHO DNE (ISOLATED VIA ST.FRAGMENT)
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