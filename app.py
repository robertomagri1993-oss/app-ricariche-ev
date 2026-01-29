import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Tesla Manager", page_icon="⚡", layout="wide")

# --- PERSONALIZZAZIONE LOGO (Favicon Apple/Mobile) ---
URL_LOGO_PERSONALIZZATO = "https://i.postimg.cc/Y0n1BpM2/domohome.png" 
st.markdown(
    f"""
    <head>
        <link rel="apple-touch-icon" href="{URL_LOGO_PERSONALIZZATO}">
    </head>
    """,
    unsafe_allow_html=True
)

# --- CSS PER PULIZIA UI ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            .stApp {max-width: 100%; padding-top: 1rem;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- CONNESSIONE DATABASE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # ttl=0 forza il refresh ad ogni azione (utile per app in sviluppo/uso personale)
    try:
        df_r = conn.read(worksheet="Ricariche", ttl=0)
        df_t = conn.read(worksheet="Tariffe", ttl=0)
        df_c = conn.read(worksheet="Config", ttl=0)
        return df_r, df_t, df_c
    except Exception as e:
        st.error(f"Errore di connessione al Database: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ricariche, df_tariffe, df_config = load_data()

# --- COSTANTI ---
mesi_ita = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", 
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
RESA_EV = 6.9      # km/kWh
RESA_BENZA = 14.0  # km/L
OGGI = datetime.now()
ANNO_CORRENTE = str(OGGI.year)
MESE_CORRENTE = mesi_ita[OGGI.month - 1]

# --- FUNZIONE PULIZIA E CALCOLO ---
def get_data_full(df_r, df_t, df_c):
    if df_r is None or df_r.empty: return pd.DataFrame()
    
    # 1. Preparazione Ricariche
    df_r = df_r.copy()
    df_r['Data'] = pd.to_datetime(df_r['Data'])
    df_r['Anno'] = df_r['Data'].dt.year.astype(str)
    
    # 2. Preparazione Config (Prezzo Benzina per Anno)
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        # Pulisce l'anno convertendo float (2025.0) in stringa pulita ("2025")
        df_c_clean['Anno'] = pd.to_numeric(df_c_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)
    
    # 3. Preparazione Tariffe (Prezzo Luce per Mese E Anno)
    df_t_clean = df_t.copy() if df_t is not None and not df_t.empty else pd.DataFrame(columns=['Anno', 'Mese', 'Prezzo'])
    if not df_t_clean.empty:
        if 'Anno' not in df_t_clean.columns:
            # Fallback se manca la colonna Anno nel foglio (evita crash)
            df_t_clean['Anno'] = ANNO_CORRENTE 
        # Pulisce l'anno anche qui
        df_t_clean['Anno'] = pd.to_numeric(df_t_clean['Anno'], errors='coerce').fillna(0).astype(int).astype(str)

    # 4. Merge dei dati (Chiavi multiple: Mese E Anno)
    # Unisce Ricariche con Tariffe basandosi su Mese E Anno
    df_m = pd.merge(df_r, df_t_clean, on=['Mese', 'Anno'], how='left')
    # Unisce il risultato con il prezzo benzina dell'Anno corrispondente
    df_m = pd.merge(df_m, df_c_clean, on='Anno', how='left')
    
    # 5. Gestione Valori Mancanti e Calcoli
    df_m['Prezzo_Luce'] = pd.to_numeric(df_m['Prezzo'], errors='coerce').fillna(0)
    df_m['Prezzo_Benza'] = pd.to_numeric(df_m['Prezzo_Benzina'], errors='coerce').fillna(1.85)
    df_m['kWh'] = pd.to_numeric(df_m['kWh'], errors='coerce').fillna(0)
    
    df_m['Spesa_EV'] = df_m['kWh'] * df_m['Prezzo_Luce']
    df_m['Spesa_Benza_Eq'] = (df_m['kWh'] * RESA_EV / RESA_BENZA) * df_m['Prezzo_Benza']
    df_m['Risparmio'] = df_m['Spesa_Benza_Eq'] - df_m['Spesa_EV']
    
    return df_m

# Calcolo del DataFrame completo
df_all = get_data_full(df_ricariche, df_tariffe, df_config)

# --- INTERFACCIA UTENTE ---
tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# ==========================
# TAB 1: HOME (Inserimento)
# ==========================
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        col_inp, col_dummy = st.columns([2,1])
        kwh_in = col_inp.number_input(f"Inserisci kWh ricaricati", min_value=0.0, step=0.1, value=None, placeholder="0.0")
        
        col_reg, col_del = st.columns(2)
        
        # Tasto Registra
        if col_reg.button("REGISTRA", use_container_width=True, type="primary"):
            if kwh_in:
                nuova_r = pd.DataFrame([{
                    "Data": OGGI.strftime("%Y-%m-%d"), 
                    "kWh": kwh_in, 
                    "Mese": MESE_CORRENTE
                }])
                # Concatena e salva
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear() # Pulisce cache interna Streamlit
                st.rerun()

        # Tasto Elimina Ultima
        if col_del.button("🗑️ ELIMINA ULTIMA", use_container_width=True):
            if not df_ricariche.empty:
                df_rimosso = df_ricariche.drop(df_ricariche.index[-1])
                conn.update(worksheet="Ricariche", data=df_rimosso)
                st.cache_data.clear()
                st.warning("Ultima ricarica eliminata.")
                time.sleep(1)
                st.rerun()

    # KPI Rapidi Anno Corrente
    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        st.divider()
        c1, c2 = st.columns(2)
        risparmio_tot = df_curr['Risparmio'].sum()
        kwh_mese = df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum()
        
        c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{risparmio_tot:.2f} €")
        c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{kwh_mese:.1f}")
        
        st.caption("Andamento Spesa Elettrica Mensile:")
        st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# ==========================
# TAB 2: STORICO & CONFIG
# ==========================
with tab2:
    # --- SEZIONE RICERCA ---
    st.header("🔍 Analisi Storica")
    if not df_all.empty:
        col_sel_anno, col_sel_mese = st.columns(2)
        # Ordina anni in modo decrescente
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        # Se non ci sono anni, metti corrente
        if not anni_disp: anni_disp = [ANNO_CORRENTE]
            
        anno_ricerca = col_sel_anno.selectbox("Anno", anni_disp, key="sel_anno_search")
        mese_ricerca = col_sel_mese.selectbox("Mese", mesi_ita, key="sel_mese_search")

        df_mirato = df_all[(df_all['Anno'] == anno_ricerca) & (df_all['Mese'] == mese_ricerca)]
        
        with st.container(border=True):
            if not df_mirato.empty:
                m1, m2, m3 = st.columns(3)
                m1.metric("Energia", f"{df_mirato['kWh'].sum():.1f} kWh")
                m2.metric("Spesa EV", f"{df_mirato['Spesa_EV'].sum():.2f} €")
                m3.metric("Risparmio", f"{df_mirato['Risparmio'].sum():.2f} €", delta_color="normal")
                
                st.write(f"**Dettaglio {mese_ricerca} {anno_ricerca}:**")
                df_display = df_mirato[['Data', 'kWh', 'Spesa_EV']].copy()
                df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                # Ordina per data decrescente per una lettura migliore
                st.dataframe(
                    df_display.sort_values(by='Data', ascending=False), 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info(f"Nessun dato per {mese_ricerca} {anno_ricerca}")

    st.divider()
    st.header("⚙️ Impostazioni Economiche")
    
    # --- CONFIG PREZZO BENZINA (PER ANNO) ---
    with st.expander("⛽ Prezzo Benzina (Annuale)"):
        col_a, col_p = st.columns(2)
        # Genera lista anni dinamica (es. 2024-2030)
        range_anni = [str(y) for y in range(2024, 2031)]
        idx_anno = 2 if len(range_anni) > 2 else 0 # Cerca di selezio
