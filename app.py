import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Tesla Model 3 Manager", page_icon="⚡", layout="wide")
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

# --- LOGICA CALCOLI (Versione Blindata Multi-Anno) ---
def get_data_full(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    df_r = df_r.copy()
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    # Pulizia Anno in Config per evitare errori di merge
    df_c_c = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_c.empty:
        df_c_c['Anno'] = df_c_c['Anno'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))
    
    # Merge Dati
    df_m = pd.merge(df_r, df_t, on='Mese', how='left')
    df_m = pd.merge(df_m, df_c_c, on='Anno', how='left')
    
    # Conversione e Calcoli
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    return df_m

df_all = get_data_full(df_ricariche, df_tariffe, df_config)

tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# ==========================================
# TAB 1: HOME
# ==========================================
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        # Campo vuoto all'avvio
        kwh_in = st.number_input(f"Inserisci kWh ricaricati", min_value=0.0, step=0.1, value=None, placeholder="Scrivi qui...")
        
        if st.button("REGISTRA", use_container_width=True, type="primary"):
            if kwh_in:
                nuova_r = pd.DataFrame([{"Data": OGGI.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": MESE_CORRENTE}])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear()
                st.success("Registrato!")
                time.sleep(0.5)
                st.rerun()

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        c1, c2 = st.columns(2)
        c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
        c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum():.1f}")
        
        st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# ==========================================
# TAB 2: STORICO & CONFIG
# ==========================================
with tab2:
    st.subheader("🔍 Analisi Mensile")
    if not df_all.empty:
        col_a, col_m = st.columns(2)
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        anno_sel = col_a.selectbox("Anno", anni_disp)
        mese_sel = col_m.selectbox("Mese", mesi_ita)

        df_mirato = df_all[(df_all['Anno'] == anno_sel) & (df_all['Mese'] == mese_sel)]
        
        if not df_mirato.empty:
            m1, m2 = st.columns(2)
            m1.metric("Totale Energia", f"{df_mirato['kWh'].sum():.1f} kWh")
            m2.metric("Spesa Totale", f"{df_mirato['Spesa_EV'].sum():.2f} €")
        else:
            st.info("Nessun dato registrato.")

    st.divider()
    st.subheader("⚙️ Configurazioni")
    
    # Prezzo Benzina (Sostituisce se esistente)
    with st.expander("⛽ Prezzo Benzina per Anno"):
        col_1, col_2 = st.columns(2)
        a_target = col_1.selectbox("Seleziona Anno", [str(y) for y in range(2024, 2031)], index=2)
        p_target = col_2.number_input("Prezzo Medio (€/L)", value=1.85, format="%.3f")
        if st.button("Salva Prezzo Benzina"):
            # Pulizia e sostituzione
            df_c_clean = df_config.copy()
            if not df_c_clean.empty:
                df_c_clean['Anno'] = df_c_clean['Anno'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))
            df_final = pd.concat([df_c_clean[df_c_clean['Anno'] != a_target], 
                                  pd.DataFrame([{"Anno": a_target, "Prezzo_Benzina": p_target}])], ignore_index=True)
            conn.update(worksheet="Config", data=df_final)
            st.cache_data.clear()
            st.rerun()

    # Tariffa Luce
    with st.expander("📅 Tariffe Luce Casa"):
        m_s = st.selectbox("Seleziona Mese", mesi_ita)
        p_s = st.number_input("Tariffa (€/kWh)", min_value=0.0, step=0.01)
        if st.button("Salva Tariffa"):
            df_t_f = pd.concat([df_tariffe[df_tariffe['Mese'] != m_s], 
                                pd.DataFrame([{"Mese": m_s, "Prezzo": p_s}])], ignore_index=True)
            conn.update(worksheet="Tariffe", data=df_t_f)
            st.cache_data.clear()
            st.rerun()
