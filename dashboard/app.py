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

st.divider()
st.subheader("Wallet Trust Lookup")

with st.form("wallet_lookup_form"):
    lookup_address = st.text_input(
        "Wallet address",
        placeholder="0x...",
        help="Enter a complete Ethereum wallet address.",
    )

    lookup_submitted = st.form_submit_button(
        "Check Wallet Trust"
    )


if lookup_submitted:
    if not api_is_healthy:
        st.error(
            "The Trust API must be online before checking a wallet."
        )
    elif not API_KEY:
        st.error(
            "Configure DASHBOARD_API_KEY before checking a wallet."
        )
    elif not lookup_address.strip():
        st.warning("Enter a wallet address.")
    else:
        try:
            with st.spinner("Calculating wallet trust..."):
                trust_result = client.check_wallet(
                    lookup_address.strip()
                )

            st.session_state["selected_wallet"] = (
                lookup_address.strip()
            )
            st.session_state["trust_result"] = trust_result
            st.session_state.pop("generated_proof", None)

        except DashboardAPIError as exc:
            st.error(exc.message)


if "trust_result" in st.session_state:
    trust_result = st.session_state["trust_result"]

    st.subheader("Trust Result")

    tier_column, human_column, confidence_column = st.columns(3)

    with tier_column:
        trust_tier = trust_result.get("trust_tier", "unknown")

        st.metric(
            label="Trust Tier",
            value=str(trust_tier).title(),
        )

    with human_column:
        human_likelihood = trust_result.get(
            "human_likelihood",
            "unknown",
        )

        st.metric(
            label="Human Likelihood",
            value=str(human_likelihood).title(),
        )

    with confidence_column:
        confidence_score = trust_result.get(
            "confidence_score",
            0,
        )

        if isinstance(confidence_score, (int, float)):
            confidence_display = f"{confidence_score:.0%}"
        else:
            confidence_display = str(confidence_score)

        st.metric(
            label="Confidence",
            value=confidence_display,
        )

    risk_flags = trust_result.get("risk_flags", [])

    st.markdown("#### Risk Flags")

    if risk_flags:
        for risk_flag in risk_flags:
            st.warning(str(risk_flag).replace("_", " ").title())
    else:
        st.success("No risk flags were returned.")

    with st.expander("View complete trust response"):
        st.json(trust_result)

    st.markdown("#### Generate Signed Proof")

    valid_for_hours = st.selectbox(
        "Proof validity",
        options=[1, 6, 12, 24, 48, 72],
        index=3,
        format_func=lambda hours: f"{hours} hours",
    )

    if st.button("Generate Signed Proof"):
        selected_wallet = st.session_state.get(
            "selected_wallet"
        )

        try:
            with st.spinner("Generating signed proof..."):
                generated_proof = client.generate_proof(
                    wallet_address=selected_wallet,
                    valid_for_hours=valid_for_hours,
                )

            st.session_state["generated_proof"] = generated_proof

        except DashboardAPIError as exc:
            st.error(exc.message)


if "generated_proof" in st.session_state:
    st.success("Signed proof generated successfully.")

    with st.expander(
        "View generated proof",
        expanded=True,
    ):
        st.json(st.session_state["generated_proof"])