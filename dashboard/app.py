import os

import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import DashboardAPIError, TrustAPIClient


load_dotenv()

API_BASE_URL = os.getenv(
    "DASHBOARD_API_URL",
    "http://127.0.0.1:8000",
)
API_KEY = os.getenv("DASHBOARD_API_KEY", "")

st.set_page_config(
    page_title="Web3 Trust Dashboard",
    page_icon="🔐",
    layout="wide",
)

client = TrustAPIClient(
    base_url=API_BASE_URL,
    api_key=API_KEY,
)


st.title("Web3 Trust Dashboard")
st.caption(
    "Internal dashboard for the Proof-of-Human Trust API"
)


with st.sidebar:
    st.header("Dashboard Settings")
    st.text(f"API: {API_BASE_URL}")

    if API_KEY:
        st.success("API key configured")
    else:
        st.warning("Dashboard API key is missing")

    if st.button("Refresh dashboard"):
        st.rerun()


st.subheader("System Status")

api_is_healthy = False
health_message = "Unavailable"

try:
    health_data = client.health()
    api_is_healthy = health_data.get("status") == "healthy"
    health_message = health_data.get("status", "unknown")
except DashboardAPIError as exc:
    st.error(exc.message)


status_column, environment_column = st.columns(2)

with status_column:
    st.metric(
        label="API Status",
        value="Online" if api_is_healthy else "Offline",
    )

with environment_column:
    st.metric(
        label="Deployment",
        value="Local",
    )


st.subheader("Wallet Overview")

wallets = []
wallet_error = None

if api_is_healthy:
    try:
        wallets = client.list_wallets()
    except DashboardAPIError as exc:
        wallet_error = exc.message

total_column, source_column, health_column = st.columns(3)

with total_column:
    st.metric(
        label="Stored Wallets",
        value=len(wallets),
    )

with source_column:
    sources = {
        wallet.get("source", "unknown")
        for wallet in wallets
    }

    st.metric(
        label="Data Sources",
        value=len(sources),
    )

with health_column:
    st.metric(
        label="Health Response",
        value=health_message.title(),
    )


if wallet_error:
    st.error(wallet_error)
elif not api_is_healthy:
    st.info(
        "Start the FastAPI server to load wallet information."
    )
elif not wallets:
    st.info(
        "No wallets are currently stored in the database."
    )
else:
    st.subheader("Stored Wallets")

    st.dataframe(
        wallets,
        width="stretch",
        hide_index=True,
    )
