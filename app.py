import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="EV Manager Multi-Year", page_icon="⚡", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    df_c = conn.read(worksheet="Config", ttl=0)
    return df_r, df_t, df_c

df_ricariche, df_tariffe, df_config = load_data()
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# --- COSTANTI ---
RESA_EV = 6.9      
RESA_BENZA = 14.0  
OGGI = datetime.now()
ANNO_CORRENTE = str(OGGI.year)
MESE_CORRENTE = mesi_ita[OGGI.month - 1]

# --- LOGICA CALCOLI ---
def get_data_full(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    
    # Prepara Ricariche
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    # 1. Unisce Tariffe Luce (per Mese)
    df_m = pd.merge(df_r, df_t, on='Mese', how='left')
    
    # 2. Unisce Prezzo Benzina (per Anno)
    df_m = pd.merge(df_m, df_c, on='Anno', how='left')
    
    # Pulizia Numerica
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.82)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    # Calcoli
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    
    return df_m

df_all = get_data_full(df_ricariche, df_tariffe, df_config)

# --- INTERFACCIA TABS ---
tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# ==========================================
# TAB 1: HOME
# ==========================================
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        kwh_in = st.number_input(f"kWh ricaricati oggi", min_value=0.0, step=0.1)
        if st.button("REGISTRA", use_container_width=True, type="primary"):
            nuova_r = pd.DataFrame([{"Data": OGGI.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": MESE_CORRENTE}])
            df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
            conn.update(worksheet="Ricariche", data=df_invio)
            st.cache_data.clear()
            st.rerun()

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        st.metric(f"💰 Risparmio Totale {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
        st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# ==========================================
# TAB 2: STORICO & CONFIG
# ==========================================
with tab2:
    st.header("📊 Analisi Storica")
    if not df_all.empty:
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        anno_sel = st.selectbox("Seleziona Anno", anni_disp)
        df_st = df_all[df_all['Anno'] == anno_sel]
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Risparmio {anno_sel}", f"{df_st['Risparmio'].sum():.2f} €")
        c2.metric("kWh Totali", f"{df_st['kWh'].sum():.1f}")
        c3.metric("Benzina Media", f"{df_st['Prezzo_Benza'].mean():.3f} €/L")

    st.divider()
    st.header("⚙️ Configurazioni")
    
    # Configurazione Benzina per Anno
    with st.expander("⛽ Prezzi Benzina per Anno"):
        col_anno, col_prezzo = st.columns(2)
        a_set = col_anno.selectbox("Anno", [str(y) for y in range(2024, 2030)], index=2)
        p_set = col_prezzo.number_input("Prezzo Medio (€/L)", value=1.82, format="%.3f")
        if st.button("Salva Prezzo Anno"):
            df_c_new = pd.concat([df_config[df_config['Anno'] != a_set], 
                                  pd.DataFrame([{"Anno": a_set, "Prezzo_Benzina": p_set}])], ignore_index=True)
            conn.update(worksheet="Config", data=df_c_new)
            st.cache_data.clear()
            st.rerun()

    # Tariffe Luce
    with st.expander("📅 Tariffe Luce Mensili"):
        m_s = st.selectbox("Mese", mesi_ita)
        p_s = st.number_input("Prezzo (€/kWh)", min_value=0.0, step=0.01)
        if st.button("Aggiorna Tariffa"):
            df_t_f = pd.concat([df_tariffe[df_tariffe['Mese'] != m_s], 
                                pd.DataFrame([{"Mese": m_s, "Prezzo": p_s}])], ignore_index=True)
            conn.update(worksheet="Tariffe", data=df_t_f)
            st.cache_data.clear()
            st.rerun()
