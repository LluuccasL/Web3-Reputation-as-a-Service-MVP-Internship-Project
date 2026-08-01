import networkx as nx
import pytest

from app.demo_wallets import (
    COMMON_SYBIL_RECIPIENTS,
    DEMO_ADDRESS_BY_KEY,
    SHARED_SYBIL_FUNDER,
    get_demo_enriched_data,
)
from app.services.transaction_graph import (
    build_transaction_graph,
    build_wallet_relationship_graph,
    graph_to_dict,
)
from app.services.wallet_relationships import (
    extract_wallet_relationships,
)


def _profile(scenario_key: str) -> dict:
    enriched_data = get_demo_enriched_data(
        DEMO_ADDRESS_BY_KEY[scenario_key]
    )

    assert enriched_data is not None
    return extract_wallet_relationships(enriched_data)


def _sybil_profiles() -> list[dict]:
    return [
        _profile("sybil_alpha"),
        _profile("sybil_beta"),
        _profile("sybil_gamma"),
    ]


def test_builds_directed_sybil_activity_graph():
    graph = build_transaction_graph(
        _sybil_profiles()
    )

    assert isinstance(graph, nx.DiGraph)
    assert graph.number_of_nodes() == 6
    assert graph.number_of_edges() == 9
    assert graph.nodes[SHARED_SYBIL_FUNDER][
        "roles"
    ] == ["funder"]

    for recipient in COMMON_SYBIL_RECIPIENTS:
        assert graph.nodes[recipient]["roles"] == [
            "recipient"
        ]


def test_builds_complete_sybil_wallet_graph():
    graph = build_wallet_relationship_graph(
        _sybil_profiles()
    )

    assert isinstance(graph, nx.Graph)
    assert graph.number_of_nodes() == 3
    assert graph.number_of_edges() == 3

    for _, _, edge in graph.edges(data=True):
        assert edge["relationship_strength"] == 0.8
        assert edge["evidence_types"] == [
            "shared_funder",
            "shared_recipient",
            "coordinated_timing",
        ]


def test_keeps_independent_wallets_disconnected():
    graph = build_wallet_relationship_graph(
        [
            _profile("established_human"),
            _profile("normal_active"),
        ]
    )

    assert graph.number_of_nodes() == 2
    assert graph.number_of_edges() == 0


def test_serializes_graph_for_api_and_dashboard():
    graph_data = graph_to_dict(
        build_wallet_relationship_graph(
            _sybil_profiles()
        )
    )

    assert graph_data["directed"] is False
    assert graph_data["node_count"] == 3
    assert graph_data["edge_count"] == 3
    assert len(graph_data["nodes"]) == 3
    assert len(graph_data["edges"]) == 3


def test_rejects_duplicate_wallet_profiles():
    profile = _profile("sybil_alpha")

    with pytest.raises(
        ValueError,
        match="duplicate wallet profile",
    ):
        build_transaction_graph([profile, profile])


def test_rejects_negative_timing_window():
    with pytest.raises(
        ValueError,
        match="must be non-negative",
    ):
        build_wallet_relationship_graph(
            [_profile("sybil_alpha")],
            timing_window_seconds=-1,
        )
