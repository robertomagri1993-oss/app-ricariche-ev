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

# --- LOGICA CALCOLI ---
def get_data_full(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    df_r = df_r.copy()
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    # Pulizia Config Anno
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        df_c_clean['Anno'] = df_c_clean['Anno'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))
    
    # Merge con Tariffe Luce (per ricariche Casa) e Config Benzina
    df_m = pd.merge(df_r, df_t, on='Mese', how='left')
    df_m = pd.merge(df_m, df_c_clean, on='Anno', how='left')
    
    # Logica Prezzi Dinamica
    df_m['Prezzo_Luce_Mese'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    # CALCOLO SPESA EFFETTIVA: 
    # Se 'Tipo' è Casa usa tariffa mese, altrimenti usa il valore già presente in 'Spesa_Diretta'
    def calcola_spesa(row):
        if row['Tipo'] == 'Casa':
            return row['kWh'] * row['Prezzo_Luce_Mese']
        else:
            return pd.to_numeric(row.get('Spesa_Diretta', 0), errors='coerce')

    df_m['Spesa_EV'] = df_m.apply(calcola_spesa, axis=1)
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    return df_m

df_all = get_data_full(df_ricariche, df_tariffe, df_config)

tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# --- TAB 1: HOME ---
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    with st.container(border=True):
        col_tipo, col_kwh = st.columns(2)
        tipo_ric = col_tipo.radio("Dove hai caricato?", ["Casa", "Colonnina"], horizontal=True)
        kwh_in = col_kwh.number_input("kWh ricaricati", min_value=0.0, step=0.1, value=None, placeholder="kWh...")
        
        spesa_diretta = 0.0
        if tipo_ric == "Colonnina":
            spesa_diretta = st.number_input("Quanto hai pagato in totale? (€)", min_value=0.0, step=0.1, format="%.2f")

        if st.button("REGISTRA", use_container_width=True, type="primary"):
            if kwh_in:
                nuova_r = pd.DataFrame([{
                    "Data": OGGI.strftime("%Y-%m-%d"), 
                    "kWh": kwh_in, 
                    "Mese": MESE_CORRENTE,
                    "Tipo": tipo_ric,
                    "Spesa_Diretta": spesa_diretta if tipo_ric == "Colonnina" else 0
                }])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear()
                st.success(f"Registrata ricarica {tipo_ric}!")
                time.sleep(0.5)
                st.rerun()

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        c1, c2 = st.columns(2)
        c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
        c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum():.1f}")
        
        # Grafico spesa diviso per Tipo
        st.subheader("Distribuzione Spesa Mensile (€)")
        chart_data = df_curr.groupby(['Mese', 'Tipo'])['Spesa_EV'].sum().unstack().fillna(0)
        st.bar_chart(chart_data)

# --- TAB 2: STORICO & CONFIG ---
with tab2:
    st.header("🔍 Riepilogo Mensile Mirato")
    if not df_all.empty:
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        col_sel_anno, col_sel_mese = st.columns(2)
        anno_ricerca = col_sel_anno.selectbox("Seleziona Anno", anni_disp)
        mese_ricerca = col_sel_mese.selectbox("Seleziona Mese", mesi_ita)

        df_mirato = df_all[(df_all['Anno'] == anno_ricerca) & (df_all['Mese'] == mese_ricerca)]
        
        with st.container(border=True):
            if not df_mirato.empty:
                m1, m2, m3 = st.columns(3)
                m1.metric("Energia", f"{df_mirato['kWh'].sum():.1f} kWh")
                m2.metric("Spesa Effettiva", f"{df_mirato['Spesa_EV'].sum():.2f} €")
                m3.metric("Risparmio", f"{df_mirato['Risparmio'].sum():.2f} €")
                st.dataframe(df_mirato[['Data', 'Tipo', 'kWh', 'Spesa_EV']], use_container_width=True, hide_index=True)
            else:
                st.warning("Nessun dato per questo periodo")

    st.divider()
    st.header("⚙️ Configurazioni")
    
    with st.expander("⛽ Imposta Prezzo Benzina per Anno"):
        col_a, col_p = st.columns(2)
        target_year = col_a.selectbox("Anno", [str(y) for y in range(2024, 2031)], index=2)
        target_price = col_p.number_input("Prezzo Medio (€/L)", value=1.85, format="%.3f")
        if st.button("Salva Prezzo Anno"):
            df_config_clean = df_config.copy()
            if not df_config_clean.empty:
                df_config_clean['Anno'] = df_config_clean['Anno'].astype(str)
            df_f = pd.concat([df_config_clean[df_config_clean['Anno'] != str(target_year)], 
                              pd.DataFrame([{"Anno": str(target_year), "Prezzo_Benzina": target_price}])], ignore_index=True)
            conn.update(worksheet="Config", data=df_f)
            st.cache_data.clear()
            st.rerun()

    with st.expander("📅 Tariffe Luce CASA (Mensili)"):
        m_s = st.selectbox("Mese Luce", mesi_ita)
        p_s = st.number_input("Tua Tariffa Casa (€/kWh)", min_value=0.0, step=0.01)
        if st.button("Salva Tariffa Casa"):
            df_t_f = pd.concat([df_tariffe[df_tariffe['Mese'] != m_s], pd.DataFrame([{"Mese": m_s, "Prezzo": p_s}])], ignore_index=True)
            conn.update(worksheet="Tariffe", data=df_t_f)
            st.cache_data.clear()
            st.rerun()
