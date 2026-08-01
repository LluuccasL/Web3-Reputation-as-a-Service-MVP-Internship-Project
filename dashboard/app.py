import os

import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import DashboardAPIError
from dashboard.sybil_client import SybilAPIClient
from dashboard.sybil_integration import (
    flagged_wallet_rows,
    merge_trust_and_sybil_results,
    stored_wallet_addresses,
    sybil_context_for_wallet,
)


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

client = SybilAPIClient(
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

    sybil_context = sybil_context_for_wallet(
        st.session_state.get(
            "analytics_sybil_result"
        ),
        trust_result.get("wallet_address"),
    )

    if sybil_context:
        st.markdown("#### Stored-Wallet Sybil Context")

        sybil_score_column, sybil_level_column, cluster_column = (
            st.columns(3)
        )

        with sybil_score_column:
            st.metric(
                "Sybil Risk Score",
                f"{sybil_context.get('sybil_risk_score', 0)}/100",
            )

        with sybil_level_column:
            st.metric(
                "Sybil Risk Level",
                str(
                    sybil_context.get(
                        "sybil_risk_level",
                        "low",
                    )
                ).title(),
            )

        with cluster_column:
            st.metric(
                "Related Stored Wallets",
                len(
                    sybil_context.get(
                        "related_wallets",
                        [],
                    )
                ),
            )

        cluster_id = sybil_context.get(
            "cluster_id"
        )

        if cluster_id:
            st.warning(
                "This wallet belongs to detected cluster "
                f"`{cluster_id}` within the most recent "
                "stored-wallet analysis."
            )
        else:
            st.success(
                "This wallet was not clustered with another "
                "stored wallet."
            )

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
st.divider()
st.subheader("Trust Analytics")

if not api_is_healthy:
    st.info("Start the Trust API to load analytics.")
elif not API_KEY:
    st.warning("Configure DASHBOARD_API_KEY to load analytics.")
elif not wallets:
    st.info("Add wallets to the database to view analytics.")
else:
    if st.button("Analyze Stored Wallets"):
        analytics_results = []
        analytics_errors = []
        analytics_sybil_result = None
        analytics_sybil_error = None

        progress_bar = st.progress(0)
        progress_text = st.empty()

        for index, wallet in enumerate(wallets):
            wallet_address = (
                wallet.get("wallet_address")
                or wallet.get("address")
            )

            progress_text.text(
                f"Analyzing wallet {index + 1} of {len(wallets)}"
            )

            if not wallet_address:
                analytics_errors.append(
                    "A stored wallet did not contain an address."
                )
                continue

            try:
                result = client.check_wallet(wallet_address)

                analytics_results.append(
                    {
                        "wallet_address": wallet_address,
                        "trust_tier": result.get(
                            "trust_tier",
                            "unknown",
                        ),
                        "human_likelihood": result.get(
                            "human_likelihood",
                            "unknown",
                        ),
                        "confidence_score": result.get(
                            "confidence_score",
                            0,
                        ),
                        "risk_flags": result.get(
                            "risk_flags",
                            [],
                        ),
                    }
                )
            except DashboardAPIError as exc:
                analytics_errors.append(
                    f"{wallet_address}: {exc.message}"
                )

            progress_bar.progress((index + 1) / len(wallets))

        progress_text.empty()
        progress_bar.empty()

        try:
            analyzed_addresses = (
                stored_wallet_addresses(
                    analytics_results
                )
            )

            if len(analyzed_addresses) >= 2:
                with st.spinner(
                    "Comparing stored wallets for Sybil behavior..."
                ):
                    analytics_sybil_result = (
                        client.analyze_sybil_wallets(
                            analyzed_addresses
                        )
                    )
            elif analyzed_addresses:
                analytics_sybil_error = (
                    "At least two successfully analyzed stored "
                    "wallets are required for Sybil comparison."
                )

        except (
            DashboardAPIError,
            ValueError,
        ) as exc:
            analytics_sybil_error = (
                exc.message
                if isinstance(
                    exc,
                    DashboardAPIError,
                )
                else str(exc)
            )

        analytics_results = (
            merge_trust_and_sybil_results(
                analytics_results,
                analytics_sybil_result,
            )
        )

        st.session_state["analytics_results"] = analytics_results
        st.session_state["analytics_errors"] = analytics_errors
        st.session_state[
            "analytics_sybil_result"
        ] = analytics_sybil_result
        st.session_state[
            "analytics_sybil_error"
        ] = analytics_sybil_error


if "analytics_results" in st.session_state:
    analytics_results = st.session_state["analytics_results"]
    analytics_errors = st.session_state.get(
        "analytics_errors",
        [],
    )

    if analytics_results:
        tier_counts = {}

        for result in analytics_results:
            tier = str(result["trust_tier"]).title()
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        st.markdown("#### Trust-Tier Distribution")
        st.bar_chart(tier_counts)

        flagged_wallets = flagged_wallet_rows(
            analytics_results
        )
        analytics_sybil_result = (
            st.session_state.get(
                "analytics_sybil_result"
            )
        )
        cluster_count = (
            analytics_sybil_result.get(
                "cluster_count",
                0,
            )
            if isinstance(
                analytics_sybil_result,
                dict,
            )
            else 0
        )
        sybil_flagged_count = sum(
            1
            for result in analytics_results
            if result.get("sybil_cluster_id")
        )

        (
            analyzed_column,
            flagged_column,
            sybil_wallet_column,
            cluster_column,
        ) = st.columns(4)

        with analyzed_column:
            st.metric(
                "Wallets Analyzed",
                len(analytics_results),
            )

        with flagged_column:
            st.metric(
                "Flagged Wallets",
                len(flagged_wallets),
            )

        with sybil_wallet_column:
            st.metric(
                "Sybil-Clustered Wallets",
                sybil_flagged_count,
            )

        with cluster_column:
            st.metric(
                "Sybil Clusters",
                cluster_count,
            )

        st.markdown("#### Flagged or Low-Trust Wallets")

        if flagged_wallets:
            tier_filter = st.multiselect(
                "Filter by trust tier",
                options=sorted(
                    {
                        str(wallet["trust_tier"])
                        for wallet in flagged_wallets
                    }
                ),
            )

            filtered_wallets = flagged_wallets

            if tier_filter:
                filtered_wallets = [
                    wallet
                    for wallet in flagged_wallets
                    if str(wallet["trust_tier"]) in tier_filter
                ]

            st.dataframe(
                filtered_wallets,
                width="stretch",
                hide_index=True,
            )
        else:
            st.success(
                "No flagged or low-trust wallets were found."
            )

    analytics_sybil_error = st.session_state.get(
        "analytics_sybil_error"
    )

    if analytics_sybil_error:
        st.info(
            "Stored-wallet Sybil comparison was not available: "
            f"{analytics_sybil_error}"
        )

    if analytics_errors:
        with st.expander("Analytics errors"):
            for error in analytics_errors:
                st.error(error)


st.divider()
st.header("Advanced Bot Detection")
st.caption(
    "Analyze transaction behavior, bot-risk signals, "
    "data coverage, and explainable score adjustments."
)

selected_wallet = st.session_state.get(
    "selected_wallet"
)

trust_result = st.session_state.get(
    "trust_result"
)

if (
    not selected_wallet
    and isinstance(trust_result, dict)
):
    selected_wallet = trust_result.get(
        "wallet_address"
    )

if not selected_wallet:
    st.info(
        "Use Wallet Lookup above before running "
        "the enhanced behavioral analysis."
    )
else:
    st.write(f"Selected wallet: `{selected_wallet}`")

    if st.button(
        "Run enhanced analysis",
        type="primary",
        key="run_enhanced_analysis",
    ):
        try:
            with st.spinner(
                "Analyzing blockchain behavior..."
            ):
                enhanced_result = (
                    client.check_wallet_enhanced(
                        selected_wallet
                    )
                )

            st.session_state[
                "enhanced_result"
            ] = enhanced_result

            st.session_state[
                "enhanced_wallet"
            ] = selected_wallet

        except DashboardAPIError as exc:
            st.error(str(exc))

enhanced_result = st.session_state.get(
    "enhanced_result"
)

enhanced_wallet = st.session_state.get(
    "enhanced_wallet"
)

if (
    isinstance(enhanced_result, dict)
    and enhanced_wallet == selected_wallet
):
    st.subheader("Enhanced trust result")

    score_column, tier_column, risk_column = (
        st.columns(3)
    )

    with score_column:
        st.metric(
            "Enhanced score",
            enhanced_result.get(
                "enhanced_score",
                0,
            ),
            delta=enhanced_result.get(
                "score_adjustment",
                0,
            ),
            help=(
                "The delta shows the change from "
                "the original trust score."
            ),
        )

    with tier_column:
        st.metric(
            "Trust tier",
            str(
                enhanced_result.get(
                    "trust_tier",
                    "unknown",
                )
            ).title(),
        )

    with risk_column:
        st.metric(
            "Risk level",
            str(
                enhanced_result.get(
                    "risk_level",
                    "none",
                )
            ).title(),
        )

    base_column, likelihood_column, coverage_column = (
        st.columns(3)
    )

    with base_column:
        st.metric(
            "Original score",
            enhanced_result.get(
                "base_score",
                0,
            ),
        )

    with likelihood_column:
        st.metric(
            "Human likelihood",
            str(
                enhanced_result.get(
                    "human_likelihood",
                    "unknown",
                )
            ).title(),
        )

    with coverage_column:
        coverage = float(
            enhanced_result.get(
                "data_coverage",
                0.0,
            )
        )

        st.metric(
            "Data coverage",
            f"{coverage:.0%}",
        )

    risk_points_column, penalty_column, positive_column = (
        st.columns(3)
    )

    with risk_points_column:
        st.metric(
            "Risk points",
            enhanced_result.get(
                "risk_points",
                0,
            ),
        )

    with penalty_column:
        st.metric(
            "Risk penalty",
            enhanced_result.get(
                "risk_penalty",
                0,
            ),
        )

    with positive_column:
        st.metric(
            "Positive points",
            enhanced_result.get(
                "positive_points",
                0,
            ),
        )

    st.subheader("Advanced behavioral features")

    features = enhanced_result.get(
        "advanced_features",
        {},
    )

    feature_labels = {
        "total_transfers": "Total transfers",
        "unique_interaction_addresses": (
            "Unique interaction addresses"
        ),
        "transaction_diversity": (
            "Transaction diversity"
        ),
        "unique_contracts": "Unique contracts",
        "contract_interaction_count": (
            "Contract interactions"
        ),
        "contract_interaction_ratio": (
            "Contract interaction ratio"
        ),
        "transaction_entropy": (
            "Transaction entropy"
        ),
        "wallet_lifespan_days": (
            "Wallet lifespan in days"
        ),
        "nft_transfer_count": (
            "NFT transfer count"
        ),
        "has_nft_activity": (
            "Has NFT activity"
        ),
    }

    feature_rows = [
        {
            "Feature": feature_labels.get(
                feature_name,
                feature_name,
            ),
            "Value": feature_value,
        }
        for feature_name, feature_value
        in features.items()
    ]

    st.dataframe(
        feature_rows,
        width="stretch",
        hide_index=True,
    )

    st.subheader("Risk flags")

    risk_flags = enhanced_result.get(
        "risk_flags",
        [],
    )

    if risk_flags:
        for flag in risk_flags:
            flag_name = str(
                flag.get(
                    "flag_id",
                    "unknown_flag",
                )
            ).replace("_", " ").title()

            severity = str(
                flag.get(
                    "severity",
                    "unknown",
                )
            ).upper()

            with st.expander(
                f"{severity} — {flag_name}",
                expanded=True,
            ):
                st.write(
                    flag.get(
                        "evidence",
                        "No evidence provided.",
                    )
                )

                metrics = flag.get(
                    "metrics",
                    {},
                )

                if metrics:
                    st.json(metrics)
    else:
        st.success(
            "No behavioral risk flags were detected."
        )

    informational_flags = enhanced_result.get(
        "informational_flags",
        [],
    )

    if informational_flags:
        st.subheader("Informational signals")

        for flag in informational_flags:
            flag_name = str(
                flag.get(
                    "flag_id",
                    "information",
                )
            ).replace("_", " ").title()

            with st.expander(flag_name):
                st.write(
                    flag.get(
                        "evidence",
                        "No evidence provided.",
                    )
                )

                metrics = flag.get(
                    "metrics",
                    {},
                )

                if metrics:
                    st.json(metrics)

    st.subheader("Score explanation")

    score_factors = enhanced_result.get(
        "score_factors",
        [],
    )

    if score_factors:
        factor_rows = [
            {
                "Factor": str(
                    factor.get(
                        "factor_id",
                        "unknown",
                    )
                ).replace("_", " ").title(),
                "Direction": str(
                    factor.get(
                        "direction",
                        "unknown",
                    )
                ).title(),
                "Points": factor.get(
                    "points",
                    0,
                ),
                "Evidence": factor.get(
                    "evidence",
                    "",
                ),
            }
            for factor in score_factors
        ]

        st.dataframe(
            factor_rows,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info(
            "No score adjustments were applied."
        )

    st.subheader("Data-source availability")

    source_status = enhanced_result.get(
        "source_status",
        {},
    )

    source_rows = [
        {
            "Source": source.replace(
                "_",
                " ",
            ).title(),
            "Status": str(status).title(),
        }
        for source, status in source_status.items()
    ]

    if source_rows:
        st.dataframe(
            source_rows,
            width="stretch",
            hide_index=True,
        )

    data_errors = enhanced_result.get(
        "data_errors",
        {},
    )

    if data_errors:
        with st.expander(
            "Unavailable or partial data sources"
        ):
            for source, message in data_errors.items():
                st.warning(
                    f"{source.replace('_', ' ').title()}: "
                    f"{message}"
                )


try:
    demo_catalog = client.get_demo_wallets()
except DashboardAPIError as exc:
    demo_catalog = {
        "demo_mode_enabled": False,
        "wallets": [],
    }

    st.sidebar.warning(
        f"Demo scenarios are unavailable: {exc}"
    )


if demo_catalog.get("demo_mode_enabled"):
    demo_wallets = demo_catalog.get(
        "wallets",
        [],
    )

    if demo_wallets:
        st.sidebar.divider()
        st.sidebar.subheader("Demo Wallet Scenarios")

        st.sidebar.warning(
            "These wallets use synthetic demonstration data."
        )

        demo_wallet_by_key = {
            wallet["scenario_key"]: wallet
            for wallet in demo_wallets
        }

        demo_scenario_keys = list(
            demo_wallet_by_key
        )

        selected_demo_key = st.sidebar.selectbox(
            "Choose a scenario",
            options=demo_scenario_keys,
            format_func=lambda scenario_key: (
                demo_wallet_by_key[
                    scenario_key
                ]["label"]
            ),
            key="selected_demo_scenario",
        )

        selected_demo = demo_wallet_by_key[
            selected_demo_key
        ]

        st.sidebar.caption(
            selected_demo["description"]
        )

        st.sidebar.code(
            selected_demo["address"],
            language=None,
        )

        with st.sidebar.expander(
            "Expected demonstration"
        ):
            st.write(
                selected_demo[
                    "expected_outcome"
                ]
            )

            if selected_demo.get("group_id"):
                st.write(
                    "Related group: "
                    f"`{selected_demo['group_id']}`"
                )

        if st.sidebar.button(
            "Use this demo wallet",
            type="primary",
            key="use_demo_wallet",
        ):
            st.session_state[
                "selected_wallet"
            ] = selected_demo["address"]

            st.session_state[
                "selected_demo_wallet"
            ] = selected_demo

            st.session_state.pop(
                "enhanced_result",
                None,
            )

            st.session_state.pop(
                "enhanced_wallet",
                None,
            )

            st.rerun()

        active_demo = st.session_state.get(
            "selected_demo_wallet"
        )

        if (
            isinstance(active_demo, dict)
            and st.session_state.get(
                "selected_wallet"
            ) == active_demo.get("address")
        ):
            st.sidebar.success(
                "Selected: "
                f"{active_demo['label']}"
            )
else:
    st.sidebar.info(
        "Set DEMO_MODE=true and restart Uvicorn "
        "to enable synthetic wallet scenarios."
    )
