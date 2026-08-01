from itertools import combinations
from typing import Any

import networkx as nx

from app.services.wallet_relationships import (
    DEFAULT_TIMING_WINDOW_SECONDS,
    compare_wallet_relationships,
)


ACTIVITY_RELATIONSHIPS = (
    ("funders", "funder", "funded", True),
    ("recipients", "recipient", "transferred_to", False),
    ("contracts", "contract", "interacted_with", False),
)

RELATIONSHIP_WEIGHTS = {
    "shared_funder": 0.40,
    "shared_recipient": 0.10,
    "shared_contract": 0.10,
    "coordinated_timing": 0.04,
}

RELATIONSHIP_CAPS = {
    "shared_recipient": 0.20,
    "shared_contract": 0.20,
    "coordinated_timing": 0.20,
}


def _normalized_values(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    return sorted(
        {
            value.strip().lower()
            for value in values
            if isinstance(value, str) and value.strip()
        }
    )


def _validated_profiles(
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    addresses: set[str] = set()

    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError(
                "each relationship profile must be a dictionary"
            )

        address = profile.get("address")

        if not isinstance(address, str) or not address.strip():
            raise ValueError(
                "each relationship profile must contain an address"
            )

        address = address.strip().lower()

        if address in addresses:
            raise ValueError(
                f"duplicate wallet profile: {address}"
            )

        addresses.add(address)
        validated.append({**profile, "address": address})

    return sorted(
        validated,
        key=lambda profile: profile["address"],
    )


def _add_entity_role(
    graph: nx.DiGraph,
    address: str,
    role: str,
    analyzed_wallets: set[str],
) -> None:
    if graph.has_node(address):
        roles = set(graph.nodes[address].get("roles") or [])
        roles.add(role)
        graph.nodes[address]["roles"] = sorted(roles)
        return

    graph.add_node(
        address,
        node_type=(
            "wallet"
            if address in analyzed_wallets
            else "external_entity"
        ),
        roles=[role],
    )


def _add_activity_edge(
    graph: nx.DiGraph,
    source: str,
    target: str,
    relationship_type: str,
) -> None:
    if graph.has_edge(source, target):
        relationship_types = set(
            graph.edges[source, target].get(
                "relationship_types",
                [],
            )
        )
        relationship_types.add(relationship_type)
        graph.edges[source, target][
            "relationship_types"
        ] = sorted(relationship_types)
        return

    graph.add_edge(
        source,
        target,
        relationship_types=[relationship_type],
    )


def build_transaction_graph(
    profiles: list[dict[str, Any]],
) -> nx.DiGraph:
    """
    Build a directed graph of wallets and external entities.
    """
    profiles = _validated_profiles(profiles)
    analyzed_wallets = {
        profile["address"]
        for profile in profiles
    }
    graph = nx.DiGraph()

    for profile in profiles:
        graph.add_node(
            profile["address"],
            node_type="wallet",
            roles=["analyzed_wallet"],
        )

    for profile in profiles:
        wallet = profile["address"]

        for field, role, relation, points_to_wallet in (
            ACTIVITY_RELATIONSHIPS
        ):
            for entity in _normalized_values(
                profile.get(field)
            ):
                _add_entity_role(
                    graph,
                    entity,
                    role,
                    analyzed_wallets,
                )

                source, target = (
                    (entity, wallet)
                    if points_to_wallet
                    else (wallet, entity)
                )

                _add_activity_edge(
                    graph,
                    source,
                    target,
                    relation,
                )

    return graph


def calculate_relationship_strength(
    comparison: dict[str, Any],
) -> float:
    """
    Convert shared evidence counts to a normalized 0-to-1 weight.
    """
    score = (
        len(comparison.get("shared_funders") or [])
        * RELATIONSHIP_WEIGHTS["shared_funder"]
    )

    for field, evidence_type in (
        ("shared_recipients", "shared_recipient"),
        ("shared_contracts", "shared_contract"),
    ):
        score += min(
            len(comparison.get(field) or [])
            * RELATIONSHIP_WEIGHTS[evidence_type],
            RELATIONSHIP_CAPS[evidence_type],
        )

    timing_count = int(
        comparison.get(
            "coordinated_outgoing_transfers",
            0,
        )
        or 0
    )

    score += min(
        timing_count
        * RELATIONSHIP_WEIGHTS["coordinated_timing"],
        RELATIONSHIP_CAPS["coordinated_timing"],
    )

    return round(min(score, 1.0), 4)


def build_wallet_relationship_graph(
    profiles: list[dict[str, Any]],
    timing_window_seconds: int = (
        DEFAULT_TIMING_WINDOW_SECONDS
    ),
) -> nx.Graph:
    """
    Project shared evidence into an undirected wallet graph.
    """
    if timing_window_seconds < 0:
        raise ValueError(
            "timing_window_seconds must be non-negative"
        )

    profiles = _validated_profiles(profiles)
    graph = nx.Graph()

    for profile in profiles:
        graph.add_node(
            profile["address"],
            node_type="wallet",
        )

    for left, right in combinations(profiles, 2):
        comparison = compare_wallet_relationships(
            left,
            right,
            timing_window_seconds=timing_window_seconds,
        )

        if not comparison["has_relationship"]:
            continue

        graph.add_edge(
            left["address"],
            right["address"],
            relationship_strength=(
                calculate_relationship_strength(comparison)
            ),
            evidence_types=comparison["evidence_types"],
            shared_funders=comparison["shared_funders"],
            shared_recipients=(
                comparison["shared_recipients"]
            ),
            shared_contracts=comparison["shared_contracts"],
            shared_counterparties=(
                comparison["shared_counterparties"]
            ),
            coordinated_outgoing_transfers=(
                comparison[
                    "coordinated_outgoing_transfers"
                ]
            ),
        )

    return graph


def graph_to_dict(
    graph: nx.Graph,
) -> dict[str, Any]:
    """
    Convert a graph to deterministic API/UI-friendly data.
    """
    nodes = [
        {"id": node_id, **attributes}
        for node_id, attributes in sorted(
            graph.nodes(data=True),
            key=lambda item: item[0],
        )
    ]

    edges = [
        {
            "source": source,
            "target": target,
            **attributes,
        }
        for source, target, attributes in sorted(
            graph.edges(data=True),
            key=lambda item: (item[0], item[1]),
        )
    ]

    return {
        "directed": graph.is_directed(),
        "nodes": nodes,
        "edges": edges,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
    }
