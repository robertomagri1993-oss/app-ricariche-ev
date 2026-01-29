import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Home Charge", page_icon="⚡", layout="wide")

# --- CONNESSIONE DATABASE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    df_c = conn.read(worksheet="Config", ttl=0)
    return df_r, df_t, df_c

df_ricariche, df_tariffe, df_config = load_data()
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# --- COSTANTI FISSE ---
RESA_EV = 6.9      
RESA_BENZA = 14.0  
OGGI = datetime.now()
ANNO_CORRENTE = str(OGGI.year)
MESE_CORRENTE = mesi_ita[OGGI.month - 1]

# --- LOGICA CALCOLI ---
def get_data_full(df_r, df_t, df_c):
    if df_r is None or df_r.empty: 
        return pd.DataFrame()
    
    df_r = df_r.copy()
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        df_c_clean['Anno'] = df_c_clean['Anno'].astype(str)
    
    df_m = pd.merge(df_r, df_t, on='Mese', how='left')
    df_m = pd.merge(df_m, df_c_clean, on='Anno', how='left')
    
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    
    return df_m

df_all = get_data_full(df_ricariche, df_tariffe, df_config)

# --- INTERFACCIA TABS ---
tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# ==========================================
# TAB 1: HOME (MODIFICATA)
# ==========================================
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        # value=None rende il campo vuoto all'avvio
        kwh_in = st.number_input(f"Inserisci kWh ricaricati", min_value=0.0, step=0.1, value=None, placeholder="Scrivi qui i kWh...")
        
        if st.button("REGISTRA", use_container_width=True, type="primary"):
            if kwh_in is not None and kwh_in > 0:
                nuova_r = pd.DataFrame([{"Data": OGGI.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": MESE_CORRENTE}])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear()
                st.success("Salvataggio riuscito!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Inserisci un valore valido prima di salvare!")

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        if not df_curr.empty:
            c1, c2 = st.columns(2)
            c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
            c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum():.1f}")
            
            st.subheader("Spesa Mensile Corrente (€)")
            st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# ==========================================
# TAB 2: STORICO & CONFIG
# ==========================================
with tab2:
    st.header("📊 Analisi Storica Multi-Anno")
    
    if not df_all.empty:
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        anno_sel = st.selectbox("Seleziona Anno", anni_disp)
        df_st = df_all[df_all['Anno'] == anno_sel]
        
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Risparmio {anno_sel}", f"{df_st['Risparmio'].sum():.2f} €")
        c2.metric("Energia Totale", f"{df_st['kWh'].sum():.1f} kWh")
        c3.metric("Spesa Benzina Eq.", f"{df_st['Spesa_Benza_Eq'].sum():.2f} €")
        
        with st.expander(f"Dettaglio ricariche {anno_sel}"):
            st.dataframe(df_st[['Data', 'kWh', 'Mese', 'Spesa_EV', 'Risparmio']], use_container_width=True, hide_index=True)

    st.divider()
    st.header("⚙️ Configurazioni")
    
    with st.expander("⛽ Prezzi Benzina per Anno"):
        col_a, col_p = st.columns(2)
        anno_target = col_a.selectbox("Anno", [str(y) for y in range(2024, 2031)], index=2)
        prezzo_target = col_p.number_input("Prezzo Medio (€/L)", value=1.850, format="%.3f")
        if st.button("Salva Prezzo Benzina"):
            df_c_new = pd.concat([df_config[df_config['Anno'].astype(str) != anno_target], 
                                  pd.DataFrame([{"Anno": anno_target, "Prezzo_Benzina": prezzo_target}])], ignore_index=True)
            conn.update(worksheet="Config", data=df_c_new)
            st.cache_data.clear()
            st.success(f"Prezzo {anno_target} aggiornato!")
            st.rerun()

    with st.expander("📅 Tariffe Luce Mensili"):
        m_s = st.selectbox("Mese", mesi_ita)
        p_s = st.number_input("Tua Tariffa (€/kWh)", min_value=0.0, step=0.01)
        if st.button("Aggiorna Tariffa Luce"):
            df_t_f = pd.concat([df_tariffe[df_tariffe['Mese'] != m_s], 
                                pd.DataFrame([{"Mese": m_s, "Prezzo": p_s}])], ignore_index=True)
            conn.update(worksheet="Tariffe", data=df_t_f)
            st.cache_data.clear()
            st.success(f"Tariffa {m_s} aggiornata!")
            st.rerun()
