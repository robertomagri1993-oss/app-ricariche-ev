import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# Configurazione Pagina
st.set_page_config(page_title="EV Expense Tracker", page_icon="⚡", layout="centered")

# 1. Connessione al database
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    return df_r, df_t

df_ricariche, df_tariffe = load_data()

mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# 2. Funzione Ricalcolo Dinamico
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

# --- INTERFACCIA ---
st.title("⚡ My EV Manager")

if st.button("🔄 Aggiorna Dati"):
    st.cache_data.clear()
    st.rerun()

# --- SEZIONE 1: NUOVA RICARICA ---
with st.container(border=True):
    oggi = datetime.now()
    nome_mese_oggi = mesi_ita[oggi.month - 1]
    st.subheader(f"Registra per {nome_mese_oggi}")
    kwh_in = st.number_input("kWh caricati", min_value=0.0, step=0.1, format="%.1f")
    
    if st.button("SALVA RICARICA", use_container_width=True, type="primary"):
        nuova_r = pd.DataFrame([{"Data": oggi.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": nome_mese_oggi}])
        df_invio = pd.concat([df_ricariche[["Data", "kWh", "Mese"]], nuova_r], ignore_index=True)
        conn.update(worksheet="Ricariche", data=df_invio)
        st.success("Salvataggio riuscito!")
        st.cache_data.clear()
        time.sleep(1)
        st.rerun()

# --- SEZIONE 2: GRAFICO SPESA MENSILE ---
st.divider()
if not df_visualizzazione.empty:
    st.subheader("📊 Spesa Totale Mensile (€)")
    
    # Raggruppiamo la spesa per mese
    df_mensile = df_visualizzazione.groupby('Mese')['Spesa'].sum().reset_index()
    
    # Ordiniamo i mesi cronologicamente per il grafico
    df_mensile['Mese_Idx'] = df_mensile['Mese'].apply(lambda x: mesi_ita.index(x))
    df_mensile = df_mensile.sort_values('Mese_Idx')
    
    # Visualizzazione grafico a barre
    st.bar_chart(df_mensile.set_index('Mese')['Spesa'])

# --- SEZIONE 3: ANALISI DETTAGLIATA ---
st.divider()
if not df_visualizzazione.empty:
    mesi_disponibili = df_visualizzazione['Mese'].unique()
    mese_analisi = st.selectbox("Dettaglio Mese", mesi_disponibili, index=len(mesi_disponibili)-1)
    
    df_mese = df_visualizzazione[df_visualizzazione['Mese'] == mese_analisi]
    
    c1, c2 = st.columns(2)
    c1.metric("Spesa Mese", f"{df_mese['Spesa'].sum():.2f} €")
    c2.metric("Energia Mese", f"{df_mese['kWh'].sum():.1f} kWh")
    
    with st.expander("Vedi singole ricariche"):
        st.dataframe(df_mese[["Data", "kWh", "Spesa"]], use_container_width=True, hide_index=True)

# --- SEZIONE 4: GESTIONE TARIFFE ---
st.divider()
with st.expander("⚙️ Imposta Prezzi kWh"):
    m_sel = st.selectbox("Mese", mesi_ita)
    p_sel = st.number_input("Prezzo (€/kWh)", min_value=0.0, step=0.01, format="%.2f")
    
    if st.button("Aggiorna Tariffa"):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        df_t_clean = df_tariffe[df_tariffe['Mese'] != m_sel] if not df_tariffe.empty else df_tariffe
        df_t_final = pd.concat([df_t_clean, nuova_t], ignore_index=True)
        conn.update(worksheet="Tariffe", data=df_t_final)
        st.cache_data.clear()
        st.success("Tariffa aggiornata!")
        time.sleep(1)
        st.rerun()
