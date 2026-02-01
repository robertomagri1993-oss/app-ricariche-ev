import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx
import base64

# ==========================================
# 1. FUNZIONE PER ICONE INCORPORATE (Base64)
# ==========================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

FILE_FAVICON = "favicon.ico"
FILE_APPLE_ICON = "apple-touch-icon.png"

b64_favicon = get_base64_of_bin_file(FILE_FAVICON)
b64_apple = get_base64_of_bin_file(FILE_APPLE_ICON)

if b64_favicon:
    favicon_href = f"data:image/x-icon;base64,{b64_favicon}"
else:
    favicon_href = "https://cdn-icons-png.flaticon.com/512/5969/5969249.png" 

if b64_apple:
    apple_href = f"data:image/png;base64,{b64_apple}"
else:
    apple_href = favicon_href 

# ==========================================
# 2. CONFIGURAZIONE PAGINA
# ==========================================
st.set_page_config(
    page_title="Tesla Manager", 
    page_icon=favicon_href, 
    layout="wide"
)

# ==========================================
# 3. HTML HEADER PER IPHONE
# ==========================================
st.markdown(
f"""
<head>
<link rel="apple-touch-icon" href="{apple_href}">
<link rel="apple-touch-icon" sizes="180x180" href="{apple_href}">
<link rel="icon" type="image/x-icon" href="{favicon_href}">
<link rel="shortcut icon" type="image/x-icon" href="{favicon_href}">

<meta property="og:title" content="Tesla Manager">
<meta property="og:description" content="Gestione ricariche domestiche">
<meta property="og:image" content="{apple_href}">
<meta property="og:type" content="website">

<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Tesla Manager">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
</head>
<style>
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}
.stAppDeployButton {{display:none;}}
.stApp {{max-width: 100%; padding-top: 1rem;}}

/* CSS OPZIONALE: forza anche i bottoni (Registra/Elimina) a stare affiancati */
[data-testid="stHorizontalBlock"] {{
    flex-wrap: nowrap !important;
}}
[data-testid="column"] {{
    min-width: 10px !important;
}}
</style>
""",
    unsafe_allow_html=True
)

# ==========================================
# 4. GESTIONE LOGIN
# ==========================================
def login_manager():
    st.markdown("""<style>.stApp {align-items: center; justify-content: center;}</style>""", unsafe_allow_html=True)
    cookie_manager = stx.CookieManager()
    cookie_name = "tesla_manager_auth_v3" 
    
    time.sleep(0.1) 
    cookie_value = cookie_manager.get(cookie=cookie_name)
    
    if cookie_value == st.secrets["PASSWORD"]:
        st.markdown("""<style>.stApp {align-items: unset; justify-content: unset;}</style>""", unsafe_allow_html=True)
        return True
    
    st.title("🔒 Area Riservata")
    
    with st.form("login_form"):
        username_input = st.text_input("Nome Utente")
        password_input = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Accedi")
        
        if submit_btn:
            user_ok = username_input == st.secrets["USERNAME"]
            pass_ok = password_input == st.secrets["PASSWORD"]
            
            if user_ok and pass_ok:
                expires = datetime.now() + timedelta(days=30)
                cookie_manager.set(cookie_name, password_input, expires_at=expires)
                st.success(f"Benvenuto {username_input}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Dati errati")
    return False

if not login_manager():
    st.stop()

# ==========================================
# 5. APP DATI
# ==========================================

conn = st.connection("gsheets", type=GSheetsConnection)

mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
OGGI = datetime.now()
ANNO_CORRENTE = str(OGGI.year)
MESE_CORRENTE = mesi_ita[OGGI.month - 1]

@st.cache_data(ttl=600)
def fetch_raw_data():
    try:
        df_r = conn.read(worksheet="Ricariche")
        df_t = conn.read(worksheet="Tariffe")
        df_c = conn.read(worksheet="Config")
        return df_r, df_t, df_c
    except Exception as e:
        st.error(f"Errore DB: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

@st.cache_data
def compute_analytics(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    df_r = df_r.copy()
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        df_c_clean['Anno'] = pd.to_numeric(df_c_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)
    
    df_t_clean = df_t.copy() if df_t is not None and not df_t.empty else pd.DataFrame(columns=['Anno', 'Mese', 'Prezzo'])
    if not df_t_clean.empty:
        if 'Anno' not in df_t_clean.columns: df_t_clean['Anno'] = ANNO_CORRENTE
        df_t_clean['Anno'] = pd.to_numeric(df_t_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)

    df_m = pd.merge(df_r, df_t_clean, on=['Mese', 'Anno'], how='left')
    df_m = pd.merge(df_m, df_c_clean, on='Anno', how='left')
    
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    RESA_EV = 6.9; RESA_BENZA = 14.0   
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    return df_m

df_ricariche, df_tariffe, df_config = fetch_raw_data()
df_all = compute_analytics(df_ricariche, df_tariffe, df_config)

tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        col_inp, col_dummy = st.columns([2,1])
        kwh_in = col_inp.number_input(f"Inserisci kWh", min_value=0.0, step=0.1, value=None, placeholder="0.0")
        col_reg, col_del = st.columns(2)
        if col_reg.button("✅ REGISTRA", use_container_width=True, type="primary"):
            if kwh_in is not None and kwh_in > 0:
                nuova_r = pd.DataFrame([{"Data": OGGI.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": MESE_CORRENTE}])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear(); st.rerun()
            elif kwh_in is None: st.toast("⚠️ Inserisci valore!")
        if col_del.button("🗑️ ELIMINA ULTIMA", use_container_width=True):
            if not df_ricariche.empty:
                df_rimosso = df_ricariche.drop(df_ricariche.index[-1])
                conn.update(worksheet="Ricariche", data=df_rimosso)
                st.cache_data.clear(); st.warning("
