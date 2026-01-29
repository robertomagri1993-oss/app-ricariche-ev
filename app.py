import streamlit as st
import pandas as pd
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAZIONE PAGINA ---
# Sostituisci l'emoji con l'URL del tuo logo per l'icona del browser (favicon)
st.set_page_config(page_title="Tesla Manager", page_icon="⚡", layout="wide")

# --- PERSONALIZZAZIONE LOGO IPHONE (APPLE TOUCH ICON) ---
# INCOLLA IL LINK DEL TUO LOGO DOVE C'È "IL_TUO_LINK_QUI"
URL_LOGO_PERSONALIZZATO = "<a href='https://postimg.cc/4HcKzRYj' target='_blank'><img src='https://i.postimg.cc/4HcKzRYj/domohome.png' border='0' alt='domohome'></a>" 

st.markdown(
    f"""
    <head>
        <link rel="apple-touch-icon" href="{URL_LOGO_PERSONALIZZATO}">
    </head>
    """,
    unsafe_allow_html=True
)

# --- CSS PER NASCONDERE IL BRANDING STREAMLIT ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stAppDeployButton {display:none;}
            /* Rende l'app più simile a un'app nativa su mobile */
            .stApp {
                max-width: 100%;
                padding-top: 1rem;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

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
    
    df_c_clean = df_c.copy() if df_c is not None and not df_c.empty else pd.DataFrame(columns=['Anno', 'Prezzo_Benzina'])
    if not df_c_clean.empty:
        df_c_clean['Anno'] = df_c_clean['Anno'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))
    
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

tab1, tab2 = st.tabs(["🏠 Home", "📊 Storico & Config"])

# --- TAB 1: HOME ---
with tab1:
    st.title(f"⚡ Tesla Manager {ANNO_CORRENTE}")
    
    with st.container(border=True):
        kwh_in = st.number_input(f"Inserisci kWh ricaricati", min_value=0.0, step=0.1, value=None, placeholder="kWh...")
        col_reg, col_del = st.columns(2)
        
        if col_reg.button("REGISTRA", use_container_width=True, type="primary"):
            if kwh_in:
                nuova_r = pd.DataFrame([{"Data": OGGI.strftime("%Y-%m-%d"), "kWh": kwh_in, "Mese": MESE_CORRENTE}])
                df_invio = pd.concat([df_ricariche, nuova_r], ignore_index=True)
                conn.update(worksheet="Ricariche", data=df_invio)
                st.cache_data.clear()
                st.rerun()

        if col_del.button("🗑️ ELIMINA ULTIMA", use_container_width=True):
            if not df_ricariche.empty:
                df_rimosso = df_ricariche.drop(df_ricariche.index[-1])
                conn.update(worksheet="Ricariche", data=df_rimosso)
                st.cache_data.clear()
                st.warning("Ultima ricarica eliminata.")
                time.sleep(1)
                st.rerun()

    if not df_all.empty:
        df_curr = df_all[df_all['Anno'] == ANNO_CORRENTE]
        c1, c2 = st.columns(2)
        c1.metric(f"💰 Risparmio {ANNO_CORRENTE}", f"{df_curr['Risparmio'].sum():.2f} €")
        c2.metric(f"🔌 kWh {MESE_CORRENTE}", f"{df_curr[df_curr['Mese'] == MESE_CORRENTE]['kWh'].sum():.1f}")
        st.bar_chart(df_curr.groupby('Mese')['Spesa_EV'].sum())

# --- TAB 2: STORICO & CONFIG ---
with tab2:
    st.header("🔍 Riepilogo Mensile Mirato")
    if not df_all.empty:
        col_sel_anno, col_sel_mese = st.columns(2)
        anni_disp = sorted(df_all['Anno'].unique(), reverse=True)
        anno_ricerca = col_sel_anno.selectbox("Seleziona Anno", anni_disp, key="sel_anno_search")
        mese_ricerca = col_sel_mese.selectbox("Seleziona Mese", mesi_ita, key="sel_mese_search")

        df_mirato = df_all[(df_all['Anno'] == anno_ricerca) & (df_all['Mese'] == mese_ricerca)]
        
        with st.container(border=True):
            if not df_mirato.empty:
                m1, m2 = st.columns(2)
                m1.metric(f"Energia {mese_ricerca}", f"{df_mirato['kWh'].sum():.1f} kWh")
                m2.metric(f"Spesa {mese_ricerca}", f"{df_mirato['Spesa_EV'].sum():.2f} €")
                
                st.write(f"**Dettaglio ricariche di {mese_ricerca} {anno_ricerca}:**")
                df_display = df_mirato[['Data', 'kWh']].copy()
                df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_display.sort_index(ascending=False), use_container_width=True, hide_index=True)
            else:
                st.warning(f"Nessuna ricarica registrata per {mese_ricerca} {anno_ricerca}")

    st.divider()
    st.header("⚙️ Configurazioni")
    
    with st.expander("⛽ Imposta Prezzo Benzina per Anno"):
        col_a, col_p = st.columns(2)
        target_year = col_a.selectbox("Anno", [str(y) for y in range(2024, 2031)], index=2)
        target_price = col_p.number_input("Prezzo Medio (€/L)", value=1.85, format="%.3f")
        
        if st.button("Salva Prezzo Anno"):
            df_config_clean = df_config.copy()
            if not df_config_clean.empty:
                df_config_clean['Anno'] = df_config_clean['Anno'].apply(lambda x: str(int(float(x))) if str(x).replace('.','').isdigit() else str(x))
            df_filtered = df_config_clean[df_config_clean['Anno'] != str(target_year)]
            new_entry = pd.DataFrame([{"Anno": str(target_year), "Prezzo_Benzina": target_price}])
            df_final_config = pd.concat([df_filtered, new_entry], ignore_index=True)
            conn.update(worksheet="Config", data=df_final_config)
            st.cache_data.clear()
            st.success(f"Prezzo per l'anno {target_year} aggiornato correttamente!")
            time.sleep(1)
            st.rerun()

    with st.expander("📅 Tariffe Luce Mensili"):
        m_s = st.selectbox("Mese", mesi_ita)
        p_s = st.number_input("Prezzo (€/kWh)", min_value=0.0, step=0.01)
        if st.button("Salva Tariffa Luce"):
            df_t_f = pd.concat([df_tariffe[df_tariffe['Mese'] != m_s], pd.DataFrame([{"Mese": m_s, "Prezzo": p_s}])], ignore_index=True)
            conn.update(worksheet="Tariffe", data=df_t_f)
            st.cache_data.clear()
            st.rerun()
