import hashlib
from itertools import combinations
from typing import Any

import networkx as nx

from app.services.behavior_fingerprint import (
    HIGH_SIMILARITY_THRESHOLD,
    calculate_behavior_similarity,
    generate_behavior_fingerprint,
)
from app.services.transaction_graph import (
    build_wallet_relationship_graph,
    graph_to_dict,
)
from app.services.wallet_relationships import (
    DEFAULT_TIMING_WINDOW_SECONDS,
    extract_wallet_relationships,
)


MIN_RELATIONSHIP_STRENGTH = 0.40

RISK_FLAG_WEIGHTS = {
    "shared_funding_source": 25,
    "coordinated_timing": 20,
    "high_behavior_similarity": 25,
    "repeated_shared_recipients": 10,
    "repeated_shared_contracts": 10,
    "dense_wallet_connections": 10,
}

RISK_FLAG_EXPLANATIONS = {
    "shared_funding_source": (
        "The wallet shares a funding source with another wallet "
        "in the detected cluster."
    ),
    "coordinated_timing": (
        "Outgoing transfers closely match the timing of another "
        "wallet in the detected cluster."
    ),
    "high_behavior_similarity": (
        "The wallet has highly similar activity patterns to another "
        "wallet in the detected cluster."
    ),
    "repeated_shared_recipients": (
        "The wallet repeatedly sends assets to recipients also used "
        "by another wallet in the detected cluster."
    ),
    "repeated_shared_contracts": (
        "The wallet repeatedly interacts with contracts also used "
        "by another wallet in the detected cluster."
    ),
    "dense_wallet_connections": (
        "Most wallets in the detected cluster are strongly connected "
        "to one another."
    ),
}


def sybil_risk_level(score: int) -> str:
    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 30:
        return "medium"

    return "low"


def _normalized_address(enriched_data: dict[str, Any]) -> str:
    address = enriched_data.get("address")

    if not isinstance(address, str) or not address.strip():
        raise ValueError(
            "each enriched wallet must contain an address"
        )

    return address.strip().lower()


def _validated_wallets(
    enriched_wallets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(enriched_wallets, list) or len(
        enriched_wallets
    ) < 2:
        raise ValueError(
            "at least two enriched wallets are required"
        )

    validated: list[dict[str, Any]] = []
    addresses: set[str] = set()

    for enriched_data in enriched_wallets:
        if not isinstance(enriched_data, dict):
            raise ValueError(
                "each enriched wallet must be a dictionary"
            )

        address = _normalized_address(enriched_data)

        if address in addresses:
            raise ValueError(
                f"duplicate enriched wallet: {address}"
            )

        addresses.add(address)
        validated.append({**enriched_data, "address": address})

    return sorted(
        validated,
        key=lambda item: item["address"],
    )


def _cluster_id(addresses: list[str]) -> str:
    canonical = "|".join(sorted(addresses))
    digest = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()[:12]
    return f"sybil-{digest}"


def _build_detection_graph(
    profiles: list[dict[str, Any]],
    fingerprints: dict[str, dict[str, Any]],
    timing_window_seconds: int,
) -> nx.Graph:
    relationship_graph = build_wallet_relationship_graph(
        profiles,
        timing_window_seconds=timing_window_seconds,
    )
    detection_graph = nx.Graph()

    for profile in profiles:
        detection_graph.add_node(
            profile["address"],
            node_type="wallet",
        )

    for left, right in combinations(profiles, 2):
        left_address = left["address"]
        right_address = right["address"]
        relationship = (
            relationship_graph.get_edge_data(
                left_address,
                right_address,
            )
            or {}
        )
        similarity = calculate_behavior_similarity(
            fingerprints[left_address],
            fingerprints[right_address],
        )
        relationship_strength = float(
            relationship.get(
                "relationship_strength",
                0.0,
            )
            or 0.0
        )
        behavior_similarity = float(
            similarity["similarity_score"]
        )
        has_relationship_evidence = bool(
            relationship.get("evidence_types")
        )

        if (
            relationship_strength < MIN_RELATIONSHIP_STRENGTH
            and not (
                behavior_similarity
                >= HIGH_SIMILARITY_THRESHOLD
                and has_relationship_evidence
            )
        ):
            continue

        detection_graph.add_edge(
            left_address,
            right_address,
            relationship_strength=relationship_strength,
            behavior_similarity=behavior_similarity,
            matching_fingerprint=similarity[
                "matching_fingerprint"
            ],
            evidence_types=relationship.get(
                "evidence_types",
                [],
            ),
            shared_funders=relationship.get(
                "shared_funders",
                [],
            ),
            shared_recipients=relationship.get(
                "shared_recipients",
                [],
            ),
            shared_contracts=relationship.get(
                "shared_contracts",
                [],
            ),
            coordinated_outgoing_transfers=int(
                relationship.get(
                    "coordinated_outgoing_transfers",
                    0,
                )
                or 0
            ),
        )

    return detection_graph


def _wallet_flags(
    graph: nx.Graph,
    address: str,
    cluster_size: int,
    cluster_density: float,
) -> list[str]:
    edges = [
        attributes
        for _, _, attributes in graph.edges(
            address,
            data=True,
        )
    ]
    flags: set[str] = set()

    if any(edge["shared_funders"] for edge in edges):
        flags.add("shared_funding_source")

    if any(
        edge["coordinated_outgoing_transfers"] > 0
        for edge in edges
    ):
        flags.add("coordinated_timing")

    if any(
        edge["behavior_similarity"]
        >= HIGH_SIMILARITY_THRESHOLD
        for edge in edges
    ):
        flags.add("high_behavior_similarity")

    if any(
        len(edge["shared_recipients"]) >= 2
        for edge in edges
    ):
        flags.add("repeated_shared_recipients")

    if any(
        len(edge["shared_contracts"]) >= 2
        for edge in edges
    ):
        flags.add("repeated_shared_contracts")

    if cluster_size >= 3 and cluster_density >= 0.75:
        flags.add("dense_wallet_connections")

    return [
        flag
        for flag in RISK_FLAG_WEIGHTS
        if flag in flags
    ]


def _related_wallets(
    graph: nx.Graph,
    address: str,
) -> list[dict[str, Any]]:
    related: list[dict[str, Any]] = []

    for neighbor in sorted(graph.neighbors(address)):
        edge = graph.edges[address, neighbor]
        related.append(
            {
                "address": neighbor,
                "relationship_strength": edge[
                    "relationship_strength"
                ],
                "behavior_similarity": edge[
                    "behavior_similarity"
                ],
                "matching_fingerprint": edge[
                    "matching_fingerprint"
                ],
                "evidence_types": edge[
                    "evidence_types"
                ],
                "shared_funders": edge[
                    "shared_funders"
                ],
                "shared_recipients": edge[
                    "shared_recipients"
                ],
                "shared_contracts": edge[
                    "shared_contracts"
                ],
                "coordinated_outgoing_transfers": edge[
                    "coordinated_outgoing_transfers"
                ],
            }
        )

    return related


def _score_from_flags(flags: list[str]) -> int:
    return min(
        sum(RISK_FLAG_WEIGHTS[flag] for flag in flags),
        100,
    )


def analyze_sybil_clusters(
    enriched_wallets: list[dict[str, Any]],
    timing_window_seconds: int = (
        DEFAULT_TIMING_WINDOW_SECONDS
    ),
) -> dict[str, Any]:
    """
    Detect connected wallet clusters and return explainable risk results.
    """
    if timing_window_seconds < 0:
        raise ValueError(
            "timing_window_seconds must be non-negative"
        )

    wallets = _validated_wallets(enriched_wallets)
    profiles = [
        extract_wallet_relationships(wallet)
        for wallet in wallets
    ]
    fingerprints = {
        wallet["address"]: generate_behavior_fingerprint(
            wallet,
            relationship_profile=profile,
        )
        for wallet, profile in zip(wallets, profiles)
    }
    detection_graph = _build_detection_graph(
        profiles,
        fingerprints,
        timing_window_seconds,
    )

    cluster_by_address: dict[str, dict[str, Any]] = {}
    clusters: list[dict[str, Any]] = []

    components = sorted(
        (
            sorted(component)
            for component in nx.connected_components(
                detection_graph
            )
            if len(component) >= 2
        ),
        key=lambda component: component[0],
    )

    for addresses in components:
        subgraph = detection_graph.subgraph(addresses)
        density = round(nx.density(subgraph), 4)
        cluster_id = _cluster_id(addresses)
        cluster_data = {
            "cluster_id": cluster_id,
            "cluster_size": len(addresses),
            "wallet_addresses": addresses,
            "density": density,
        }
        clusters.append(cluster_data)

        for address in addresses:
            cluster_by_address[address] = cluster_data

    wallet_results: list[dict[str, Any]] = []

    for wallet in wallets:
        address = wallet["address"]
        cluster = cluster_by_address.get(address)

        if cluster is None:
            flags: list[str] = []
            related_wallets: list[dict[str, Any]] = []
            cluster_id = None
            cluster_size = 1
            cluster_density = 0.0
        else:
            cluster_id = cluster["cluster_id"]
            cluster_size = cluster["cluster_size"]
            cluster_density = cluster["density"]
            flags = _wallet_flags(
                detection_graph,
                address,
                cluster_size,
                cluster_density,
            )
            related_wallets = _related_wallets(
                detection_graph,
                address,
            )

        score = _score_from_flags(flags)
        wallet_results.append(
            {
                "address": address,
                "sybil_risk_score": score,
                "sybil_risk_level": sybil_risk_level(
                    score
                ),
                "cluster_id": cluster_id,
                "cluster_size": cluster_size,
                "cluster_density": cluster_density,
                "related_wallets": related_wallets,
                "risk_flags": flags,
                "explanations": [
                    RISK_FLAG_EXPLANATIONS[flag]
                    for flag in flags
                ],
                "fingerprint_id": fingerprints[address][
                    "fingerprint_id"
                ],
            }
        )

    wallet_result_by_address = {
        result["address"]: result
        for result in wallet_results
    }

    for cluster in clusters:
        cluster_results = [
            wallet_result_by_address[address]
            for address in cluster["wallet_addresses"]
        ]
        cluster_score = round(
            sum(
                result["sybil_risk_score"]
                for result in cluster_results
            )
            / len(cluster_results)
        )
        cluster_flags = [
            flag
            for flag in RISK_FLAG_WEIGHTS
            if any(
                flag in result["risk_flags"]
                for result in cluster_results
            )
        ]
        cluster.update(
            {
                "sybil_risk_score": cluster_score,
                "sybil_risk_level": sybil_risk_level(
                    cluster_score
                ),
                "risk_flags": cluster_flags,
                "explanations": [
                    RISK_FLAG_EXPLANATIONS[flag]
                    for flag in cluster_flags
                ],
            }
        )

    return {
        "analyzed_wallet_count": len(wallets),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "wallet_results": wallet_results,
        "relationship_graph": graph_to_dict(
            detection_graph
        ),
        "thresholds": {
            "minimum_relationship_strength": (
                MIN_RELATIONSHIP_STRENGTH
            ),
            "high_behavior_similarity": (
                HIGH_SIMILARITY_THRESHOLD
            ),
            "timing_window_seconds": (
                timing_window_seconds
            ),
        },
    }
