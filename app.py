import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="EV Quick Manager", page_icon="⚡", layout="wide") # Layout wide per le metriche affiancate

# --- CONNESSIONE DATABASE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    return df_r, df_t

df_ricariche, df_tariffe = load_data()
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# --- COSTANTI FISSE ---
RESA_EV = 6.9      
RESA_BENZA = 14.0  
ANNO_CORRENTE = datetime.now().year

# --- FUNZIONE PREZZO BENZINA (5 secondi di timeout) ---
@st.cache_data(ttl=86400)
def get_prezzo_benzina_bg():
    try:
        url = "https://www.mise.gov.it"
        df_b = pd.read_csv(url, sep=";", skiprows=1, encoding='latin-1', storage_options={'timeout': 5})
        prezzo_str = df_b[df_b.iloc[:,0].str.contains("Benzina", na=False)].iloc
        return float(prezzo_str.replace(',', '.')), True
    except:
        return 1.820, False # Prezzo backup 2026

# --- LOGICA CALCOLI ---
def get_data_aggiornata(df_r, df_t):
    if df_r is None or df_r.empty: 
        return pd.DataFrame(columns=['Data', 'kWh', 'Mese', 'Prezzo', 'Spesa'])
    df_r_clean = df_r[['Data', 'kWh', 'Mese']].copy()
    df_t_clean = df_t[['Mese', 'Prezzo']].copy() if not df_t.empty else pd.DataFrame(columns=['Mese', 'Prezzo'])
    df_merge = pd.merge(df_r_clean, df_t_clean, on='Mese', how='left')
    df_merge['Prezzo'] = pd.to_numeric(df_merge['Prezzo']).fillna(0)
    df_merge['kWh'] = pd.to_numeric(df_merge['kWh']).fillna(0)
    df_merge['Spesa'] = df_merge['kWh'] * df_merge['Prezzo']
    return df_merge

# --- ESECUZIONE ---
df_visualizzazione = get_data_aggiornata(df_ricariche, df_tariffe)
prezzo_benza, is_live = get_prezzo_benzina_bg()
tab_home, tab_config = st.tabs(["🏠 Registra & Home", "⚙️ Dettagli & Tariffe"])

# ==========================================
# TAB 1: HOME (PRIORITÀ ASSOLUTA ALL'INSERIMENTO)
# ==========================================
with tab_home:
    st.title(f"⚡ My EV Savings {ANNO_CORRENTE}")
    
    # 1. MODULO DI REGISTRAZIONE (Sempre reattivo)
    with st.container(border=True):
        oggi = datetime.now()
        nome_mese_oggi = mesi_ita[oggi.month - 1]
        kwh_in = st.number_input("Inserisci kWh caricati", min_value=0.0, step=0.1)
        
        if st.button("REGISTRA ORA", use_container_width=True, type="primary"):
            nuova_r = pd.DataFrame([{"Data": oggi.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": nome_mese_oggi}])
            df_invio = pd.concat([df_ricariche[["Data", "kWh", "Mese"]], nuova_r], ignore_index=True)
            conn.update(worksheet="Ricariche", data=df_invio)
            st.cache_data.clear()
            st.success("Dato inviato a Google Sheets!")
            time.sleep(0.5)
            st.rerun()

    # 2. METRICHE & RISPARMIO (Affiancate)
    if not df_visualizzazione.empty:
        # Dati annuali
        tot_kwh_anno = df_visualizzazione['kWh'].sum()
        tot_spesa_ev = df_visualizzazione['Spesa'].sum()
        km_stima = tot_kwh_anno * RESA_EV
        risparmio_totale = ((km_stima / RESA_BENZA) * prezzo_benza) - tot_spesa_ev

        # Dati mensili
        df_mese = df_visualizzazione[df_visualizzazione['Mese'] == nome_mese_oggi]
        kwh_mese_corrente = df_mese['kWh'].sum()
        spesa_mese_corrente = df_mese['Spesa'].sum()

        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="💰 Risparmio Annuale", value=f"{risparmio_totale:.2f} €")
        with col2:
            st.metric(label=f"🔌 Totale kWh {nome_mese_oggi}", value=f"{kwh_mese_corrente:.1f} kWh")
            
        st.bar_chart(df_visualizzazione.groupby('Mese')['Spesa'].sum())

# ==========================================
# TAB 2: DETTAGLI & TARIFFE
# ==========================================
with tab_config:
    st.subheader("⚙️ Parametri & Info")
    colA, colB = st.columns(2)
    with colA:
        st.metric("Tua Efficienza EV", f"{RESA_EV} km/kWh")
    with colB:
        st.metric("Auto Benzina Eq.", f"{RESA_BENZA} km/L")
        
    if is_live:
        st.success(f"✅ Prezzo Benzina Live: {prezzo_benza:.3f} €/L")
    else:
        st.info(f"ℹ️ Prezzo Benzina (Backup): {prezzo_benza:.3f} €/L")

    st.divider()
    st.subheader("📅 Tariffe Mensili")
    m_sel = st.selectbox("Seleziona Mese", mesi_ita)
    p_sel = st.number_input("Prezzo kWh (€)", min_value=0.0, step=0.01, format="%.2f")
    
    if st.button("Salva Tariffa Mese", use_container_width=True):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        df_t_final = pd.concat([df_tariffe[df_tariffe['Mese'] != m_sel], nuova_t], ignore_index=True)
        conn.update(worksheet="Tariffe", data=df_t_final)
        st.cache_data.clear()
        st.rerun()
