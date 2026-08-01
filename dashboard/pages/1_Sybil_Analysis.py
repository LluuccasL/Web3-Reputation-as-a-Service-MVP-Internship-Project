import os

import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import DashboardAPIError
from dashboard.sybil_client import SybilAPIClient
from dashboard.sybil_view import (
    CUSTOM_DEMO_PRESET,
    INDEPENDENT_PRESET,
    SYBIL_PRESET,
    demo_addresses_for_preset,
    parse_wallet_addresses,
    relationship_edge_rows,
    relationship_graph_dot,
    short_address,
    wallet_result_rows,
)


load_dotenv()

API_BASE_URL = os.getenv(
    "DASHBOARD_API_URL",
    "http://127.0.0.1:8000",
)
API_KEY = os.getenv("DASHBOARD_API_KEY", "")

st.set_page_config(
    page_title="Sybil Analysis",
    page_icon="🕸️",
    layout="wide",
)

client = SybilAPIClient(
    base_url=API_BASE_URL,
    api_key=API_KEY,
)

st.title("Sybil Cluster Analysis")
st.caption(
    "Compare wallets for shared funding, recipients, "
    "timing, contracts, and behavior fingerprints."
)

if not API_KEY:
    st.error(
        "Configure DASHBOARD_API_KEY before running "
        "Sybil analysis."
    )
    st.stop()

try:
    health_data = client.health()
except DashboardAPIError as exc:
    st.error(exc.message)
    st.stop()

if health_data.get("status") != "healthy":
    st.error("The Trust API is not healthy.")
    st.stop()

try:
    demo_catalog = client.get_demo_wallets()
except DashboardAPIError:
    demo_catalog = {
        "demo_mode_enabled": False,
        "wallets": [],
    }

demo_mode_enabled = bool(
    demo_catalog.get("demo_mode_enabled")
)
demo_wallets = demo_catalog.get("wallets", [])

st.subheader("Select wallets")

input_options = ["Paste wallet addresses"]

if demo_mode_enabled and demo_wallets:
    input_options.insert(0, "Demo scenarios")

input_mode = st.radio(
    "Wallet source",
    options=input_options,
    horizontal=True,
)

wallet_addresses: list[str] = []

if input_mode == "Demo scenarios":
    presets = [
        SYBIL_PRESET,
        INDEPENDENT_PRESET,
        CUSTOM_DEMO_PRESET,
    ]

    selected_preset = st.selectbox(
        "Demo group",
        options=presets,
        help=(
            "The Sybil preset should form one critical-risk "
            "cluster. The independent preset should form none."
        ),
    )

    selected_keys: list[str] = []

    if selected_preset == CUSTOM_DEMO_PRESET:
        wallet_by_key = {
            wallet["scenario_key"]: wallet
            for wallet in demo_wallets
        }

        selected_keys = st.multiselect(
            "Demo wallets",
            options=list(wallet_by_key),
            format_func=lambda key: wallet_by_key[key][
                "label"
            ],
        )

    wallet_addresses = demo_addresses_for_preset(
        demo_wallets,
        selected_preset,
        selected_scenario_keys=selected_keys,
    )

    selected_wallet_by_address = {
        wallet["address"]: wallet
        for wallet in demo_wallets
    }

    selected_rows = [
        {
            "Scenario": selected_wallet_by_address[
                address
            ]["label"],
            "Wallet": address,
            "Expected Outcome": (
                selected_wallet_by_address[address][
                    "expected_outcome"
                ]
            ),
        }
        for address in wallet_addresses
        if address in selected_wallet_by_address
    ]

    if selected_rows:
        st.dataframe(
            selected_rows,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Choose at least two demo wallets.")
else:
    address_input = st.text_area(
        "Wallet addresses",
        height=150,
        placeholder=(
            "Enter 2–25 Ethereum wallet addresses, "
            "separated by new lines or commas."
        ),
    )

timing_window_seconds = st.number_input(
    "Coordinated timing window (seconds)",
    min_value=0,
    max_value=86400,
    value=300,
    step=60,
    help=(
        "Outgoing transfers within this interval can count "
        "as coordinated timing evidence."
    ),
)

if st.button(
    "Analyze Wallet Group",
    type="primary",
):
    try:
        if input_mode == "Paste wallet addresses":
            wallet_addresses = parse_wallet_addresses(
                address_input
            )
        elif len(wallet_addresses) < 2:
            raise ValueError(
                "Choose at least two demo wallets."
            )

        with st.spinner(
            "Building relationships and detecting clusters..."
        ):
            analysis_result = (
                client.analyze_sybil_wallets(
                    wallet_addresses=wallet_addresses,
                    timing_window_seconds=int(
                        timing_window_seconds
                    ),
                )
            )

        st.session_state[
            "sybil_analysis_result"
        ] = analysis_result

    except (
        DashboardAPIError,
        ValueError,
    ) as exc:
        message = (
            exc.message
            if isinstance(exc, DashboardAPIError)
            else str(exc)
        )
        st.error(message)

analysis_result = st.session_state.get(
    "sybil_analysis_result"
)

if not isinstance(analysis_result, dict):
    st.info(
        "Choose a wallet group and run the analysis "
        "to view clusters."
    )
    st.stop()

st.divider()
st.header("Analysis Results")

wallet_results = analysis_result.get(
    "wallet_results",
    [],
)
clusters = analysis_result.get("clusters", [])
relationship_graph = analysis_result.get(
    "relationship_graph",
    {},
)

highest_risk = max(
    (
        int(result.get("sybil_risk_score", 0))
        for result in wallet_results
    ),
    default=0,
)

wallet_column, cluster_column, risk_column, edge_column = (
    st.columns(4)
)

with wallet_column:
    st.metric(
        "Wallets Analyzed",
        analysis_result.get(
            "analyzed_wallet_count",
            0,
        ),
    )

with cluster_column:
    st.metric(
        "Clusters Detected",
        analysis_result.get(
            "cluster_count",
            0,
        ),
    )

with risk_column:
    st.metric(
        "Highest Risk Score",
        f"{highest_risk}/100",
    )

with edge_column:
    st.metric(
        "Strong Relationships",
        relationship_graph.get(
            "edge_count",
            0,
        ),
    )

if clusters:
    st.error(
        f"Detected {len(clusters)} potential Sybil "
        f"{'cluster' if len(clusters) == 1 else 'clusters'}."
    )

    st.subheader("Detected Clusters")

    for cluster in clusters:
        title = (
            f"{cluster['cluster_id']} — "
            f"{str(cluster['sybil_risk_level']).title()} risk"
        )

        with st.expander(title, expanded=True):
            size_column, score_column, density_column = (
                st.columns(3)
            )

            with size_column:
                st.metric(
                    "Cluster Size",
                    cluster["cluster_size"],
                )

            with score_column:
                st.metric(
                    "Risk Score",
                    f"{cluster['sybil_risk_score']}/100",
                )

            with density_column:
                st.metric(
                    "Connection Density",
                    f"{cluster['density']:.0%}",
                )

            st.write("Wallets")

            for address in cluster[
                "wallet_addresses"
            ]:
                st.code(address, language=None)

            st.write("Risk evidence")

            for explanation in cluster.get(
                "explanations",
                [],
            ):
                st.warning(explanation)
else:
    st.success(
        "No Sybil clusters were detected in this wallet group."
    )

st.subheader("Wallet Risk Results")

st.dataframe(
    wallet_result_rows(wallet_results),
    width="stretch",
    hide_index=True,
)

if wallet_results:
    result_by_address = {
        result["address"]: result
        for result in wallet_results
    }

    inspected_address = st.selectbox(
        "Inspect one wallet",
        options=list(result_by_address),
        format_func=short_address,
    )

    inspected_result = result_by_address[
        inspected_address
    ]

    detail_column, fingerprint_column = st.columns(2)

    with detail_column:
        st.write(
            "Cluster:",
            inspected_result.get(
                "cluster_id"
            )
            or "Not clustered",
        )

        st.write(
            "Related wallets:",
            len(
                inspected_result.get(
                    "related_wallets",
                    [],
                )
            ),
        )

    with fingerprint_column:
        st.write("Behavior fingerprint")

        st.code(
            inspected_result.get(
                "fingerprint_id",
                "",
            ),
            language=None,
        )

    explanations = inspected_result.get(
        "explanations",
        [],
    )

    if explanations:
        for explanation in explanations:
            st.warning(explanation)
    else:
        st.success(
            "No Sybil risk flags were assigned to this wallet."
        )

    related_wallets = inspected_result.get(
        "related_wallets",
        [],
    )

    if related_wallets:
        st.dataframe(
            [
                {
                    "Related Wallet": short_address(
                        related["address"]
                    ),
                    "Relationship Strength": related[
                        "relationship_strength"
                    ],
                    "Behavior Similarity": related[
                        "behavior_similarity"
                    ],
                    "Evidence": ", ".join(
                        evidence.replace(
                            "_",
                            " ",
                        ).title()
                        for evidence in related[
                            "evidence_types"
                        ]
                    ),
                }
                for related in related_wallets
            ],
            width="stretch",
            hide_index=True,
        )

st.subheader("Wallet Relationship Graph")

st.caption(
    "Thicker lines represent stronger relationship evidence. "
    "Node colors represent each wallet's Sybil risk level."
)

st.graphviz_chart(
    relationship_graph_dot(
        relationship_graph,
        wallet_results,
    ),
    width="stretch",
    height=460,
)

edge_rows = relationship_edge_rows(
    relationship_graph
)

if edge_rows:
    with st.expander(
        "View relationship-edge evidence"
    ):
        st.dataframe(
            edge_rows,
            width="stretch",
            hide_index=True,
        )
else:
    st.info(
        "The graph contains isolated wallets and no "
        "strong relationship edges."
    )

with st.expander("View complete Sybil response"):
    st.json(analysis_result)
