import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import time

# Configurazione Pagina
st.set_page_config(page_title="EV Manager PRO", page_icon="⚡", layout="centered")

# 1. Connessione al database (ttl=0 forza l'aggiornamento continuo)
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Carichiamo i dati con ttl=0 per evitare che Streamlit mostri dati vecchi
    df_r = conn.read(worksheet="Ricariche", ttl=0)
    df_t = conn.read(worksheet="Tariffe", ttl=0)
    return df_r, df_t

df_ricariche, df_tariffe = load_data()

# Mesi in Italiano
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]

# 2. Funzione Ricalcolo Dinamico
def get_data_aggiornata(df_r, df_t):
    if df_r is None or df_r.empty: 
        return pd.DataFrame(columns=['Data', 'kWh', 'Mese', 'Prezzo', 'Spesa'])
    
    # Assicuriamoci che le colonne siano pulite
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

# Pulsante di Sincronizzazione Manuale
if st.button("🔄 Sincronizza ora"):
    st.cache_data.clear()
    st.rerun()

# --- SEZIONE 1: NUOVA RICARICA ---
with st.container(border=True):
    oggi = datetime.now()
    nome_mese_oggi = mesi_ita[oggi.month - 1]
    st.subheader(f"Registra per {nome_mese_oggi}")
    
    kwh_in = st.number_input("kWh caricati", min_value=0.0, step=0.1, format="%.1f")
    
    if st.button("SALVA RICARICA", use_container_width=True, type="primary"):
        # Preparazione riga
        nuova_r = pd.DataFrame([{
            "Data": oggi.strftime("%Y-%m-%d"), 
            "kWh": kwh_in, 
            "Mese": nome_mese_oggi
        }])
        
        # Unione e invio a Google
        df_invio = pd.concat([df_ricariche[["Data", "kWh", "Mese"]], nuova_r], ignore_index=True)
        conn.update(worksheet="Ricariche", data=df_invio)
        
        # Reset Cache e Ricaricamento
        st.success("Salvataggio riuscito!")
        st.cache_data.clear()
        time.sleep(1) # Piccolo delay per permettere a Google di processare
        st.rerun()

# --- SEZIONE 2: ANALISI E GRAFICO ---
st.divider()
if not df_tariffe.empty:
    st.subheader("📈 Trend Tariffa (€/kWh)")
    df_tariffe['Mese_Num'] = df_tariffe['Mese'].apply(lambda x: mesi_ita.index(x) if x in mesi_ita else 99)
    df_plot = df_tariffe.sort_values('Mese_Num')
    st.line_chart(df_plot.set_index('Mese')['Prezzo'])

if not df_visualizzazione.empty:
    st.subheader("📊 Analisi Spese")
    # Menu a tendina con i mesi presenti nel database
    mesi_disponibili = df_visualizzazione['Mese'].unique()
    mese_analisi = st.selectbox("Seleziona Mese", mesi_disponibili, index=len(mesi_disponibili)-1)
    
    df_mese = df_visualizzazione[df_visualizzazione['Mese'] == mese_analisi]
    
    c1, c2 = st.columns(2)
    c1.metric("Totale Speso", f"{df_mese['Spesa'].sum():.2f} €")
    c2.metric("Energia Totale", f"{df_mese['kWh'].sum():.1f} kWh")
    
    with st.expander("Dettaglio Ricariche"):
        st.dataframe(df_mese[["Data", "kWh", "Prezzo", "Spesa"]], use_container_width=True, hide_index=True)

# --- SEZIONE 3: GESTIONE TARIFFE ---
st.divider()
with st.expander("⚙️ Configura Tariffe Mensili"):
    m_sel = st.selectbox("Scegli Mese", mesi_ita)
    p_sel = st.number_input("Prezzo (€/kWh)", min_value=0.0, step=0.01, format="%.2f", key="p_tarif")
    
    if st.button("Aggiorna Tariffa"):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        df_t_clean = df_tariffe[df_tariffe['Mese'] != m_sel] if not df_tariffe.empty else df_tariffe
        df_t_final = pd.concat([df_t_clean, nuova_t], ignore_index=True)
        
        conn.update(worksheet="Tariffe", data=df_t_final)
        st.cache_data.clear()
        st.success(f"Tariffa {m_sel} aggiornata!")
        time.sleep(1)
        st.rerun()
