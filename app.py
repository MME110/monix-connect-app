import streamlit as st
import pandas as pd
import plotly.express as px
from pypdf import PdfReader
import io, re, os

# Configure dashboard workspace grid cleanly
st.set_page_config(page_title="Monix Connect Core", layout="wide")

# ---------------------------------------------------------
# BRANDING LOGO INTEGRATION HEADER (CACHED FOR SPEED)
# ---------------------------------------------------------
base_user_path = os.environ.get('USERPROFILE', os.path.expanduser('~'))
master_storage_path = os.path.join(base_user_path, "Desktop", "monix_master_records.csv")

@st.cache_data(show_spinner=False)
def resolve_logo_path():
    absolute_logo_paths = [
        os.path.join(base_user_path, "OneDrive", "Desktop", "logo.png.jpg"),
        os.path.join(base_user_path, "Desktop", "logo.png.jpg"),
        os.path.join(base_user_path, "onedrive", "Desktop", "logo.png.jpg"),
        r"C:\Users\STONE\OneDrive\Desktop\logo.png.jpg",
        r"C:\Users\STONE\Desktop\logo.png.jpg",
        "logo.png.jpg"
    ]
    for path_candidate in absolute_logo_paths:
        if os.path.exists(path_candidate):
            return path_candidate
    return None

logo_file_resolved = resolve_logo_path()

if logo_file_resolved:
    try:
        st.image(logo_file_resolved, width=420)
    except Exception:
        st.title("🛡️ Monix Connect Core")
else:
    st.title("🛡️ Monix Connect Core")

st.markdown("### MarMonix MHT-60B Industrial Environmental Command Engine")
st.markdown("---")

# SIDEBAR MONITOR LIMIT SETUP PANELS
st.sidebar.header("📡 Hardware Device Parameters")
serial_input = st.sidebar.text_input("Active Logger Node ID", value="MX-60B-99812")
st.sidebar.markdown("---")
low_t = st.sidebar.number_input("Min Allowed Temp (°C)", value=2.0, step=0.5)
high_t = st.sidebar.number_input("Max Allowed Temp (°C)", value=8.0, step=0.5)
low_rh = st.sidebar.number_input("Min Allowed Humidity (%RH)", value=35.0, step=5.0)
high_rh = st.sidebar.number_input("Max Allowed Humidity (%RH)", value=65.0, step=5.0)
st.sidebar.markdown("---")
app_mode = st.sidebar.radio("Select Operational Mode", ["Ingest & Graph Dual-Channel Logs", "Parse Historical PDF Reports"])

# ---------------------------------------------------------
# MODE 1: LOG INGESTION FRAMEWORK WITH MASTER PERSISTENCE
# ---------------------------------------------------------
if app_mode == "Ingest & Graph Dual-Channel Logs":
    st.subheader("📋 Ingestion Pipeline: Temperature & Humidity Logs")
    uploaded_file = st.sidebar.file_uploader("Upload Logger Data Sheet (.csv, .xlsx, .txt)", type=["csv","xlsx","txt"])

    if uploaded_file is not None:
        try:
            # Cleanly load fresh file data stream
            raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(('.csv', '.txt')) else pd.read_excel(uploaded_file)
            
            cols = list(raw_df.columns)
            c_time = next((c for c in cols if any(t in c.lower() for t in ['time', 'timestamp', 'date'])), None)
            c_temp = next((c for c in cols if any(t in c.lower() for t in ['temp', 'celsius', '°c'])), None)
            c_rh = next((c for c in cols if any(t in c.lower() for t in ['humid', 'rh', '%'])), None)

            # Re-normalize data columns to numeric matrices safely
            processed_data = pd.DataFrame()
            
            if c_time:
                processed_data['Timestamp'] = raw_df[c_time].astype(str)
            else:
                processed_data['Timestamp'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

            if c_temp:
                processed_data['Temperature_C'] = pd.to_numeric(raw_df[c_temp].astype(str).str.replace(' °C','').str.strip(), errors='coerce')
            else:
                processed_data['Temperature_C'] = None

            if c_rh:
                processed_data['Humidity_RH'] = pd.to_numeric(raw_df[c_rh].astype(str).str.replace('%','').str.strip(), errors='coerce')
            else:
                processed_data['Humidity_RH'] = None

            # Tag metadata identifiers
            processed_data['Node_ID'] = serial_input
            processed_data['Ingestion_Session'] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

            # --- HARD DRIVE LOG PERSISTENCE PIPELINE ---
            if os.path.exists(master_storage_path):
                processed_data.to_csv(master_storage_path, mode='a', header=False, index=False)
            else:
                processed_data.to_csv(master_storage_path, mode='w', header=True, index=False)
            
            st.toast("💾 Central record updated successfully!", icon="💾")
            st.success(f"Connection Secure: Streamed logs for node {serial_input}")
            
        except Exception as e:
            st.error(f"Error parsing inbound telemetry structure: {e}")

    # Display accumulated historical records if the database exists
    if os.path.exists(master_storage_path):
        try:
            master_df = pd.read_csv(master_storage_path)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Historic Logs Saved", f"{len(master_df):,}")
            
            has_temp = 'Temperature_C' in master_df.columns and not master_df['Temperature_C'].dropna().empty
            has_rh = 'Humidity_RH' in master_df.columns and not master_df['Humidity_RH'].dropna().empty

            if has_temp:
                m2.metric("Peak Temp (All Time)", f"{master_df['Temperature_C'].max():.1f} °C", delta=f"Min: {master_df['Temperature_C'].min():.1f} °C", delta_color="inverse")
            if has_rh:
                m3.metric("Peak Humidity (All Time)", f"{master_df['Humidity_RH'].max():.1f} %", delta=f"Min: {master_df['Humidity_RH'].min():.1f} %", delta_color="inverse")

            # Alarm Threshold Validations
            v_t = len(master_df[(master_df['Temperature_C'] > high_t) | (master_df['Temperature_C'] < low_t)]) if has_temp else 0
            v_rh = len(master_df[(master_df['Humidity_RH'] > high_rh) | (master_df['Humidity_RH'] < low_rh)]) if has_rh else 0
            
            if v_t > 0 or v_rh > 0:
                st.error(f"🚨 Variance Triggered! Historical Breaches: Temp: {v_t} counts | Humidity: {v_rh} counts.")
            else:
                st.success("✅ Controlled Environment Maintained: Safe operational thresholds holding.")

            # Timeline Graph Engine
            st.subheader("📈 Dual-Axis Environmental Trend Analysis Timeline")
            y_channels = []
            if has_temp: y_channels.append('Temperature_C')
            if has_rh: y_channels.append('Humidity_RH')

            if y_channels:
                master_df['Timeline Sequence'] = master_df.index + 1
                fig = px.line(master_df, x='Timeline Sequence', y=y_channels, color='Node_ID', markers=True, title="Global Combined Storage Telemetry Stream")
                st.plotly_chart(fig, use_container_width=True)

            with st.expander("🔬 View Global Combined Storage Database"):
                st.dataframe(master_df)
                
            # Maintenance control button
            if st.button("🗑️ Clear All Historical Saved Records"):
                if os.path.exists(master_storage_path):
                    os.remove(master_storage_path)
                    st.rerun()
        except Exception as file_err:
            st.error(f"Database Read Error: {file_err}")
    else:
        st.info("👋 System idling. Feed a multi-channel log sheet file into the panel.")

# ---------------------------------------------------------
# MODE 2: REVERSE PDF READER MODULE WITH PROTECTED SCRAPING
# ---------------------------------------------------------
else:
    st.subheader("🔍 Reverse PDF Parsing Extraction Module")
    pdf_upload = st.sidebar.file_uploader("Upload Historical PDF Report File", type=["pdf"])
    
    if pdf_upload is not None:
        try:
            reader = PdfReader(pdf_upload)
            text = "".join([page.extract_text() for page in reader.pages])
            
            # Robust, case-insensitive regex pattern checks
            s_sn = re.search(r"(?:S/N|ID|Serial):\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
            s_hi = re.search(r"(?:Highest|Max|Maximum):\s*([\d.]+)", text, re.IGNORECASE)
            s_lo = re.search(r"(?:Lowest|Min|Minimum):\s*([\d.]+)", text, re.IGNORECASE)
            
            ex_sn = s_sn.group(1) if s_sn else "MHT-60B Profile Instance"
            ex_hi = s_hi.group(1) if s_hi else "N/A"
            ex_lo = s_lo.group(1) if s_lo else "N/A"
            
            r1, r2, r3 = st.columns(3)
            r1.metric("Scraped Serial S/N", ex_sn)
            r2.metric("Historical Lowest Record", ex_lo)
            r3.metric("Historical Highest Record", ex_hi)
            
            with st.expander("View Extracted Raw Text Stream Header Logs"): 
                st.text(text[:2000])
        except Exception as e:
            st.error(f"PDF Parse Processing Error: {e}")