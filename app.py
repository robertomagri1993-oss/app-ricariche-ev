import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# Configurazione Pagina
st.set_page_config(page_title="EV Savings Tracker", page_icon="💰", layout="centered")

# --- CONNESSIONE DATABASE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    return df_r, df_t

df_ricariche, df_tariffe = load_data()
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# --- FUNZIONE PREZZO BENZINA AUTOMATICO (CACHE 24H) ---
@st.cache_data(ttl=86400)
def get_prezzo_benzina_mimit():
    try:
        # Sorgente dati Open Data Ministero (Mimit)
        url = "https://www.mise.gov.it"
        # Il CSV del ministero ha spesso codifiche particolari (latin-1) e separatori ";"
        df_b = pd.read_csv(url, sep=";", skiprows=1, encoding='latin-1')
        # Pulizia nome colonna e recupero prezzo Benzina
        prezzo_str = df_b[df_b.iloc[:,0].str.contains("Benzina", na=False)].iloc[0,1]
        return float(prezzo_str.replace(',', '.'))
    except Exception as e:
        # Prezzo di backup in caso di errore server Ministero
        return 1.795

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

df_visualizzazione = get_data_aggiornata(df_ricariche, df_tariffe)
prezzo_benza_auto = get_prezzo_benzina_mimit()
anno_corrente = datetime.now().year

# --- INTERFACCIA TABS ---
tab_home, tab_config = st.tabs(["🏠 Home", "⚙️ Parametri & Tariffe"])

# ==========================================
# TAB 1: HOME (RISPARMIO & INSERIMENTO)
# ==========================================
with tab_home:
    st.title(f"⚡ Risparmio {anno_corrente}")
    
    # Parametri efficienza (salvati in sessione)
    resa_ev = st.session_state.get('resa_ev', 6.0)
    resa_benza = st.session_state.get('resa_benza', 16.0)

    if not df_visualizzazione.empty:
        # Calcolo risparmio annuale
        tot_kwh = df_visualizzazione['kWh'].sum()
        tot_spesa_ev = df_visualizzazione['Spesa'].sum()
        km_stima = tot_kwh * resa_ev
        spesa_benza_stima = (km_stima / resa_benza) * prezzo_benza_auto
        risparmio_totale = spesa_benza_stima - tot_spesa_ev

        # Card del Risparmio
        st.metric(label="💰 Risparmio Accumulato", 
                  value=f"{risparmio_totale:.2f} €", 
                  delta=f"Basato su {prezzo_benza_auto:.3f}€/L benzina")
    
    st.divider()

    # Inserimento Rapido
    with st.container(border=True):
        oggi = datetime.now()
        nome_mese_oggi = mesi_ita[oggi.month - 1]
        st.write(f"✍️ **Registra Ricarica ({nome_mese_oggi})**")
        kwh_in = st.number_input("kWh erogati", min_value=0.0, step=0.1, key="in_kwh")
        
        if st.button("SALVA DATI", use_container_width=True, type="primary"):
            nuova_r = pd.DataFrame([{"Data": oggi.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": nome_mese_oggi}])
            df_invio = pd.concat([df_ricariche[["Data", "kWh", "Mese"]], nuova_r], ignore_index=True)
            conn.update(worksheet="Ricariche", data=df_invio)
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

    # Grafico Spesa Mensile
    if not df_visualizzazione.empty:
        df_m = df_visualizzazione.groupby('Mese')['Spesa'].sum().reset_index()
        df_m['Idx'] = df_m['Mese'].apply(lambda x: mesi_ita.index(x))
        st.bar_chart(df_m.sort_values('Idx').set_index('Mese')['Spesa'])

# ==========================================
# TAB 2: CONFIGURAZIONE
# ==========================================
with tab_config:
    st.subheader("🛠️ Efficienza Veicoli")
    st.session_state['resa_ev'] = st.number_input("Tua resa EV (km/kWh)", value=6.0, help="Esempio: 6 km con 1 kWh")
    st.session_state['resa_benza'] = st.number_input("Resa Auto Benzina (km/L)", value=16.0, help="Esempio: 16 km con 1 litro")
    
    st.info(f"Prezzo benzina attuale: **{prezzo_benza_auto:.3f} €/L** (Fonte: Mimit)")

    st.divider()
    st.subheader("📅 Tariffe Energia")
    m_sel = st.selectbox("Seleziona Mese", mesi_ita)
    p_sel = st.number_input("Prezzo tuo kWh (€)", min_value=0.0, step=0.01, format="%.2f")
    
    if st.button("Aggiorna Tariffa Mese", use_container_width=True):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        df_t_final = pd.concat([df_tariffe[df_tariffe['Mese'] != m_sel], nuova_t], ignore_index=True)
        conn.update(worksheet="Tariffe", data=df_t_final)
        st.cache_data.clear()
        st.success("Prezzo aggiornato!")
        time.sleep(1)
        st.rerun()
