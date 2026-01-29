import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx
from PIL import Image  # <--- Libreria necessaria per l'icona locale

# ==========================================
# 🖼️ CARICAMENTO ICONA LOCALE
# ==========================================
# Carichiamo l'immagine direttamente dal file caricato su GitHub.
# Questo metodo è molto più affidabile dei link web.
try:
    icona_app = Image.open("domohome.png")
except FileNotFoundError:
    # Se per errore non trova il file, usa un'emoji per non bloccare l'app
    icona_app = "⚡"

# Per l'icona su iPhone/Android (Home Screen) serve comunque un URL pubblico.
# Usiamo quello che avevi all'inizio che va benissimo per i telefoni.
URL_LOGO_MOBILE = "https://i.postimg.cc/Y0n1BpM2/domohome.png"


# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="Tesla Manager", 
    page_icon=icona_app,  # <--- Qui passiamo il file, non l'URL!
    layout="wide"
)

# ==========================================
# 🍪 GESTIONE LOGIN (UTENTE + PASSWORD)
# ==========================================
def login_manager():
    # CSS per centrare il login
    st.markdown(
        """<style>.stApp {align-items: center; justify-content: center;}</style>""", 
        unsafe_allow_html=True
    )
    
    # Inizializza gestore cookie
    cookie_manager = stx.CookieManager()
    
    # Nome del cookie nel browser
    cookie_name = "tesla_manager_auth_v2"
    
    # 1. Tenta di leggere il cookie
    cookie_value = cookie_manager.get(cookie=cookie_name)
    
    # 2. Se il cookie contiene la password corretta -> ACCESSO
    if cookie_value == st.secrets["PASSWORD"]:
        # Ripristina layout standard
        st.markdown(
            """<style>.stApp {align-items: unset; justify-content: unset;}</style>""", 
            unsafe_allow_html=True
        )
        return True
    
    # 3. Altrimenti mostra Form di Login
    st.title("🔒 Area Riservata")
    
    with st.form("login_form"):
        username_input = st.text_input("Nome Utente")
        password_input = st.text_input("Password", type="password")
        
        submit_btn = st.form_submit_button("Accedi")
        
        if submit_btn:
            # Verifica nei Secrets
            user_ok = username_input == st.secrets["USERNAME"]
            pass_ok = password_input == st.secrets["PASSWORD"]
            
            if user_ok and pass_ok:
                # Salva cookie per 30 giorni
                expires = datetime.now() + timedelta(days=30)
                cookie_manager.set(cookie_name, password_input, expires_at=expires)
                st.success(f"Benvenuto {username_input}! Caricamento...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Utente o Password errati")
    
    return False

# --- BLOCCO DI SICUREZZA ---
if not login_manager():
    st.stop()


# ==========================================
# 🚀 APP VERA E PROPRIA
# ==========================================

# --- INIEZIONE HTML PER ICONE TELEFONO ---
st.markdown(
    f"""
    <head>
        <link rel="apple-touch-icon" href="{URL_LOGO_MOBILE}">
        <link rel="apple-touch-icon" sizes="180x180" href="{URL_LOGO_MOBILE}">
        <link rel="icon" type="image/png" href="{URL_LOGO_MOBILE}">
    </head>
    <style>
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        .stAppDeployButton {{display:none;}}
        .stApp {{max-width: 100%; padding-top: 1rem;}}
    </style>
    """,
    unsafe_allow_html=True
)

# --- CONNESSIONE DATABASE ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- VARIABILI GLOBALI ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
OGGI = datetime.now()
ANNO_CORRENTE = str(OGGI.year)
MESE_CORRENTE = mesi_ita[OGGI.month - 1]

# --- CACHE DEI DATI ---
@st.cache_data(ttl=600)
def fetch_raw_data():
    try:
        df_r = conn.read(worksheet="Ricariche")
        df_t = conn.read(worksheet="Tariffe")
        df_c = conn.read(worksheet="Config")
        return df_r, df_t, df_c
    except Exception as e:
        st.error(f"Errore connessione GSheets: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- CACHE DEI CALCOLI ---
@st.cache_data
def compute_analytics(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    
    # 1. Ricariche
    df_r = df_r.copy()
    df_r['Data'] = pd
