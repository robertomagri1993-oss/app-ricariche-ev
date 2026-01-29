import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# Configurazione Pagina
st.set_page_config(page_title="EV Charge Manager", page_icon="⚡", layout="centered")

# 1. Connessione al database Google Sheets
# Nota: Assicurati di avere i fogli "Ricariche" e "Tariffe" nel tuo file Google
conn = st.connection("gsheets", type=GSheetsConnection)

# Caricamento Dati
try:
    df_ricariche = conn.read(worksheet="Ricariche")
    # Convertiamo la colonna Data in formato datetime
    if not df_ricariche.empty:
        df_ricariche['Data'] = pd.to_datetime(df_ricariche['Data'])
except:
    df_ricariche = pd.DataFrame(columns=["Data", "kWh", "Spesa", "Mese"])

try:
    df_tariffe = conn.read(worksheet="Tariffe")
except:
    df_tariffe = pd.DataFrame(columns=["Mese", "Prezzo"])

# --- INTERFACCIA ---
st.title("⚡ My EV Charger")

# --- SEZIONE A: INSERIMENTO RAPIDO ---
st.subheader("Registra Ricarica")
with st.container(border=True):
    oggi = datetime.now()
    # Mappa mesi in italiano
    mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
                "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    nome_mese_oggi = mesi_ita[oggi.month - 1]

    # Recupero tariffa per il mese corrente
    tariffa_row = df_tariffe[df_tariffe['Mese'] == nome_mese_oggi]
    prezzo_kwh = tariffa_row['Prezzo'].values[0] if not tariffa_row.empty else 0.0

    kwh = st.number_input("Quanti kWh?", min_value=0.0, step=0.1, format="%.1f")
    
    costo_auto = kwh * prezzo_kwh
    st.caption(f"Tariffa {nome_mese_oggi}: {prezzo_kwh}€/kWh ⮕ **Costo: {costo_auto:.2f}€**")

    if st.button("SALVA RICARICA", use_container_width=True, type="primary"):
        nuova_riga = pd.DataFrame([{
            "Data": oggi.strftime("%Y-%m-%d"),
            "kWh": kwh,
            "Spesa": costo_auto,
            "Mese": nome_mese_oggi
        }])
        df_final = pd.concat([df_ricariche, nuova_riga], ignore_index=True)
        conn.update(worksheet="Ricariche", data=df_final)
        st.success(f"Registrato nel mese di {nome_mese_oggi}!")
        st.rerun()

# --- SEZIONE B: ANALISI SPESE ---
st.divider()
st.subheader("📊 Analisi Mensile")

elenco_mesi_registrati = df_ricariche['Mese'].unique() if not df_ricariche.empty else []

if len(elenco_mesi_registrati) > 0:
    mese_scelto = st.selectbox("Scegli il mese da analizzare", elenco_mesi_registrati)
    
    # Filtro
    df_mese = df_ricariche[df_ricariche['Mese'] == mese_scelto]
    
    # Metriche
    c1, c2 = st.columns(2)
    c1.metric("Totale Speso", f"{df_mese['Spesa'].sum():.2f} €")
    c2.metric("Energia Totale", f"{df_mese['kWh'].sum():.1f} kWh")
    
    with st.expander("Vedi dettagli ricariche"):
        st.dataframe(df_mese[["Data", "kWh", "Spesa"]], use_container_width=True, hide_index=True)
else:
    st.info("Nessun dato presente. Inizia a ricaricare!")

# --- SEZIONE C: CONFIGURAZIONE TARIFFE ---
st.divider()
with st.expander("⚙️ Imposta Prezzi kWh per Mese"):
    m_sel = st.selectbox("Seleziona Mese da configurare", mesi_ita)
    p_sel = st.number_input("Inserisci Prezzo al kWh (€)", min_value=0.0, step=0.01, format="%.2f", key="set_p")
    
    if st.button("Aggiorna Tariffa"):
        nuova_t = pd.DataFrame([{"Mese": m_sel, "Prezzo": p_sel}])
        # Rimuove vecchia voce del mese se esiste e aggiunge la nuova
        df_tariffe_clean = df_tariffe[df_tariffe['Mese'] != m_sel] if not df_tariffe.empty else df_tariffe
        df_t_final = pd.concat([df_tariffe_clean, nuova_t], ignore_index=True)
        conn.update(worksheet="Tariffe", data=df_t_final)
        st.success(f"Prezzo per {m_sel} aggiornato!")
        st.rerun()
