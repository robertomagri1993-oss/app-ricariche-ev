import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from streamlit_gsheets import GSheetsConnection
import extra_streamlit_components as stx

# --- CONFIGURAZIONE PAGINA (SEMPLICE E STABILE) ---
st.set_page_config(
    page_title="Tesla Manager", 
    page_icon="⚡", 
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
    
    cookie_manager = stx.CookieManager()
    cookie_name = "tesla_manager_auth_v2"
    
    time.sleep(0.1) # Breve pausa tecnica per lettura cookie
    cookie_value = cookie_manager.get(cookie=cookie_name)
    
    if cookie_value == st.secrets["PASSWORD"]:
        # Ripristina layout standard
        st.markdown(
            """<style>.stApp {align-items: unset; justify-content: unset;}</style>""", 
            unsafe_allow_html=True
        )
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

# --- BLOCCO DI SICUREZZA ---
if not login_manager():
    st.stop()


# ==========================================
# 🚀 APP VERA E PROPRIA
# ==========================================

# --- CSS BASE (SOLO PER NASCONDERE MENU STREAMLIT) ---
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .stAppDeployButton {display:none;}
        .stApp {max-width: 100%; padding-top: 1rem;}
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
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    # 2. Config
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        df_c_clean['Anno'] = pd.to_numeric(df_c_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)
    
    # 3. Tariffe
    df_t_clean = df_t.copy() if df_t is not None and not df_t.empty else pd.DataFrame(columns=['Anno', 'Mese', 'Prezzo'])
    if not df_t_clean.empty:
        if 'Anno' not in df_t_clean.columns: df_t_clean['Anno'] = ANNO_CORRENTE
        df_t_clean['Anno'] = pd.to_numeric(df_t_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)

    # 4. Merge
    df_m = pd.merge(df_r, df_t_clean, on=['Mese', 'Anno'], how='left')
    df_m = pd.merge(df_m, df_c_clean, on='Anno', how='left')
    
    # 5. Calcoli
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    RESA_EV = 6.9       
    RESA_BENZA = 14.0   
    
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    
    return df_m

# --- ESECUZIONE ---
df_ricariche, df_tariffe, df_config = fetch_raw_data()
df_all = compute_analytics(df_ricariche, df_tariffe, df_config)

tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# ==========================
# TAB 1: REGISTRAZIONE
# ==========================
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        col_inp, col_dummy = st.columns([2,1])
        
        kwh_in = col_inp.number_input(
            f"Inserisci kWh", 
            min_value=0.0, 
            step=0.1, 
            value=None,          
            placeholder="0.0"    
        )
        
        col_reg, col_del = st.columns(2)
        
        if col_reg.button("✅ REGISTRA", use_container_width=True, type="primary"):
            if kwh_in is not None and kwh_in > 0:
                nuova_r = pd.DataFrame([{
                    "Data": OGGI.strftime("%Y-%m-%d"), 
                    "kWh": kwh_in, 
                    "Mese": MESE_CORRENTE
                }])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear()
                st.rerun()
            elif kwh_in is None:
                st.toast("⚠️ Inserisci un valore prima di registrare!")

        if col_del.button("🗑️ ELIMINA ULTIMA", use_container_width=True):
            if not df_ricariche.empty:
                df_rimosso = df_ricariche.drop(df_ricariche.index[-1])
                conn.update(worksheet="Ricariche", data=df_rimosso)
                st.cache_data.clear()
                st.warning("Eliminata.")
                time.sleep(0.5)
                st.rerun()

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
        c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum():.1f}")
        st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# ==========================
# TAB 2: STORICO E SETTINGS
# ==========================
with tab2:
    st.header("🔍 Analisi Storica")
    if not df_all.empty:
        col_sel_anno, col_sel_mese = st.columns(2)
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True) or [ANNO_CORRENTE]
        
        anno_ricerca = col_sel_anno.selectbox("Anno", anni_disp, key="s_a")
        mese_ricerca = col_sel_mese.selectbox("Mese", mesi_ita, key="s_m")

        df_mirato = df_all[(df_all['Anno'] == anno_ricerca) & (df_all['Mese'] == mese_ricerca)]
        
        with st.container(border=True):
            if not df_mirato.empty:
                m1, m2, m3 = st.columns(3)
                m1.metric("Energia", f"{df_mirato['kWh'].sum():.1f} kWh")
                m2.metric("Spesa EV", f"{df_mirato['Spesa_EV'].sum():.2f} €")
                m3.metric("Risparmio", f"{df_mirato['Risparmio'].sum():.2f} €")
                
                df_display = df_mirato[['Data', 'kWh', 'Spesa_EV']].copy()
                df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_display.sort_values(by='Data', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info(f"Nessun dato per {mese_ricerca} {anno_ricerca}")

    st.divider()
    st.header("⚙️ Impostazioni")
    
    # --- TARIFFE LUCE ---
    with st.expander("📅 Tariffa Luce"):
        c1, c2 = st.columns(2)
        t_anno = c1.selectbox("Anno", [str(y) for y in range(2024, 2031)], index=2, key="t_a")
        t_mese = c2.selectbox("Mese", mesi_ita, key="t_m")
        t_price = st.number_input("Prezzo Luce (€/kWh)", min_value=0.0, step=0.01, format="%.3f")
        
        if st.button("Salva Tariffa"):
            df_t_temp = df_tariffe.copy()
            if 'Anno' not in df_t_temp.columns: df_t_temp['Anno'] = ""
            df_t_temp['Anno'] = pd.to_numeric(df_t_temp['Anno'], errors='coerce').fillna(0).astype(int).astype(str)
            
            mask = (df_t_temp['Mese'] == t_mese) & (df_t_temp['Anno'] == str(t_anno))
            df_filtered_t = df_t_temp[~mask]
            
            num_mese = mesi_ita.index(t_mese) + 1
            
            new_tariffa = pd.DataFrame([{
                "Mese": t_mese, 
                "Anno": str(t_anno), 
                "Prezzo": t_price,
                "mese_num": num_mese 
            }])
            
            df_final_t = pd.concat([df_filtered_t, new_tariffa], ignore_index=True)
            
            if 'mese_num' in df_final_t.columns:
                 df_final_t = df_final_t.sort_values(by=['Anno', 'mese_num'], ascending=[False, True])
            
            conn.update(worksheet="Tariffe", data=df_final_t)
            st.cache_data.clear()
            st.success(f"Tariffa salvata! ({t_mese}={num_mese})")
            time.sleep(1)
            st.rerun()

    # --- BENZINA ---
    with st.expander("⛽ Prezzo Benzina"):
        col_a, col_p = st.columns(2)
        tg_year = col_a.selectbox("Anno", [str(y) for y in range(2024, 2031)], index=2)
        tg_price = col_p.number_input("Prezzo Benzina", value=1.85, format="%.3f")
        
        if st.button("Salva Benzina"):
            df_c_t = df_config.copy()
            if not df_c_t.empty: 
                df_c_t['Anno'] = pd.to_numeric(df_c_t['Anno'], errors='coerce').fillna(0).astype(int).astype(str)
            
            df_fin = pd.concat([df_c_t[df_c_t['Anno'] != str(tg_year)], 
                               pd.DataFrame([{"Anno": str(tg_year), "Prezzo_Benzina": tg_price}])], ignore_index=True)
            conn.update(worksheet="Config", data=df_fin)
            st.cache_data.clear()
            st.rerun()
