import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="EV Dynamic Manager", page_icon="⚡")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARICAMENTO DATI ---
df_ricariche = conn.read(worksheet="Ricariche")
df_tariffe = conn.read(worksheet="Tariffe")

mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# Funzione Ricalcolo Dinamico
def get_data_aggiornata(df_r, df_t):
    if df_r.empty: return df_r
    df_merge = pd.merge(df_r.drop(columns=['Spesa'], errors='ignore'), 
                        df_t[['Mese', 'Prezzo']], on='Mese', how='left')
    df_merge['Prezzo'] = df_merge['Prezzo'].fillna(0)
    df_merge['Spesa'] = df_merge['kWh'] * df_merge['Prezzo']
    return df_merge

df_visualizzazione = get_data_aggiornata(df_ricariche, df_tariffe)

st.title("⚡ My EV Manager")

# --- SEZIONE 1: NUOVA RICARICA (Layout compatto per iPhone) ---
with st.container(border=True):
    oggi = datetime.now()
    nome_mese_oggi = mesi_ita[oggi.month - 1]
    st.subheader(f"Registra per {nome_mese_oggi}")
    kwh = st.number_input("kWh caricati", min_value=0.0, step=0.1)
    
    if st.button("SALVA RICARICA", use_container_width=True, type="primary"):
        nuova_r = pd.DataFrame([{"Data": oggi.strftime("%Y-%m-%d"), "kWh": kwh, "Mese": nome_mese_oggi}])
        df_f = pd.concat([df_ricariche[["Data", "kWh", "Mese"]], nuova_r], ignore_index=True)
        conn.update(worksheet="Ricariche", data=df_f)
        st.rerun()

# --- SEZIONE 2: ANALISI E TENDENZE ---
st.divider()
st.subheader("📊 Analisi e Trend")

if not df_tariffe.empty:
    # Grafico Variazione Tariffa
    st.write("### Andamento Prezzo kWh (€)")
    # Ordiniamo i mesi per visualizzazione cronologica corretta
    df_tariffe['Mese_Num'] = df_tariffe['Mese'].apply(lambda x: mesi_ita.index(x))
    df_plot = df_tariffe.sort_values('Mese_Num')
    st.line_chart(df_plot.set_index('Mese')['Prezzo'])

if not df_visualizzazione.empty:
    mese_analisi = st.selectbox("Seleziona Mese da analizzare", df_visualizzazione['Mese'].unique())
    df_mese = df_visualizzazione[df_visualizzazione['Mese'] == mese_analisi]
    
    col1, col2 = st.columns(2)
    col1.metric("Totale Speso", f"{df_mese['Spesa'].sum():.2f} €")
    col2.metric("Energia Totale", f"{df_mese['kWh'].sum():.1f} kWh")

# --- SEZIONE 3: CONFIGURAZIONE TARIFFE ---
st.divider()
with st.expander("⚙️ Aggiorna Tariffe Mensili"):
    m_sel = st.selectbox("Mese da modificare", mesi_ita)
    p_sel = st.number_input("Nuovo Prezzo (€/kWh)", min_value=0.0, step=0.01, format="%.2f")
    
    if st.button("Aggiorna e Ricalcola Tutto"):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        df_t_updated = pd.concat([df_tariffe[df_tariffe['Mese'] != m_sel], nuova_t], ignore_index=True)
        conn.update(worksheet="Tariffe", data=df_t_updated)
        st.success("Tutte le spese passate e future sono state aggiornate!")
        st.rerun()
