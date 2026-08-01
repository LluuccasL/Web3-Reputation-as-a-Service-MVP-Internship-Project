import re
from typing import Any


WALLET_ADDRESS_PATTERN = re.compile(
    r"^0x[a-fA-F0-9]{40}$"
)

SYBIL_PRESET = "Synthetic Sybil cluster"
INDEPENDENT_PRESET = "Independent control wallets"
CUSTOM_DEMO_PRESET = "Choose demo wallets"


def parse_wallet_addresses(raw_value: str) -> list[str]:
    """
    Parse newline, comma, or space-separated Ethereum addresses.
    """
    addresses = [
        value.strip().lower()
        for value in re.split(r"[\s,]+", raw_value)
        if value.strip()
    ]

    invalid_addresses = [
        address
        for address in addresses
        if not WALLET_ADDRESS_PATTERN.fullmatch(address)
    ]

    if invalid_addresses:
        raise ValueError(
            f"Invalid wallet address: {invalid_addresses[0]}"
        )

    if len(set(addresses)) != len(addresses):
        raise ValueError(
            "Wallet addresses must not contain duplicates."
        )

    if len(addresses) < 2:
        raise ValueError(
            "Enter at least two wallet addresses."
        )

    if len(addresses) > 25:
        raise ValueError(
            "Enter no more than 25 wallet addresses."
        )

    return addresses


def demo_addresses_for_preset(
    demo_wallets: list[dict[str, Any]],
    preset: str,
    selected_scenario_keys: list[str] | None = None,
) -> list[str]:
    """
    Resolve the selected dashboard preset to wallet addresses.
    """
    wallet_by_key = {
        wallet["scenario_key"]: wallet
        for wallet in demo_wallets
        if wallet.get("scenario_key")
        and wallet.get("address")
    }

    if preset == SYBIL_PRESET:
        selected_wallets = [
            wallet
            for wallet in demo_wallets
            if wallet.get("group_id") == "demo_sybil_cluster"
        ]
    elif preset == INDEPENDENT_PRESET:
        selected_wallets = [
            wallet_by_key[key]
            for key in (
                "established_human",
                "normal_active",
            )
            if key in wallet_by_key
        ]
    elif preset == CUSTOM_DEMO_PRESET:
        selected_wallets = [
            wallet_by_key[key]
            for key in (selected_scenario_keys or [])
            if key in wallet_by_key
        ]
    else:
        raise ValueError(
            f"Unknown demo preset: {preset}"
        )

    return [
        str(wallet["address"]).lower()
        for wallet in selected_wallets
    ]


def short_address(address: str) -> str:
    if len(address) <= 18:
        return address

    return f"{address[:10]}...{address[-6:]}"


def wallet_result_rows(
    wallet_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "Wallet": short_address(
                str(result.get("address", ""))
            ),
            "Risk Score": result.get(
                "sybil_risk_score",
                0,
            ),
            "Risk Level": str(
                result.get(
                    "sybil_risk_level",
                    "low",
                )
            ).title(),
            "Cluster": (
                result.get("cluster_id")
                or "Not clustered"
            ),
            "Related Wallets": len(
                result.get("related_wallets") or []
            ),
            "Flags": ", ".join(
                str(flag).replace("_", " ").title()
                for flag in result.get("risk_flags") or []
            )
            or "None",
        }
        for result in wallet_results
    ]


def relationship_edge_rows(
    relationship_graph: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "Wallet A": short_address(
                str(edge.get("source", ""))
            ),
            "Wallet B": short_address(
                str(edge.get("target", ""))
            ),
            "Relationship Strength": edge.get(
                "relationship_strength",
                0.0,
            ),
            "Behavior Similarity": edge.get(
                "behavior_similarity",
                0.0,
            ),
            "Matching Fingerprint": edge.get(
                "matching_fingerprint",
                False,
            ),
            "Evidence": ", ".join(
                str(evidence).replace("_", " ").title()
                for evidence in edge.get(
                    "evidence_types",
                    [],
                )
            ),
        }
        for edge in relationship_graph.get("edges", [])
    ]


def relationship_graph_dot(
    relationship_graph: dict[str, Any],
    wallet_results: list[dict[str, Any]],
) -> str:
    """
    Convert the API graph response to safe Graphviz DOT source.
    """
    risk_by_address = {
        result["address"]: result
        for result in wallet_results
        if result.get("address")
    }
    nodes = relationship_graph.get("nodes", [])
    node_id_by_address = {
        node["id"]: f"wallet_{index}"
        for index, node in enumerate(nodes)
        if node.get("id")
    }
    fill_colors = {
        "critical": "#ff6b6b",
        "high": "#ffa94d",
        "medium": "#ffe066",
        "low": "#69db7c",
    }

    lines = [
        "graph wallet_relationships {",
        '  graph [rankdir="LR", bgcolor="transparent", '
        'pad="0.3", nodesep="0.7"];',
        '  node [shape="box", style="rounded,filled", '
        'fontname="Helvetica", margin="0.16"];',
        '  edge [fontname="Helvetica", color="#6c757d"];',
    ]

    for address, graph_node_id in node_id_by_address.items():
        result = risk_by_address.get(address, {})
        risk_level = str(
            result.get("sybil_risk_level", "low")
        ).lower()
        score = int(
            result.get("sybil_risk_score", 0) or 0
        )
        label = (
            f"{short_address(address)}\\n"
            f"{risk_level.title()} · {score}/100"
        )
        fill_color = fill_colors.get(
            risk_level,
            fill_colors["low"],
        )
        lines.append(
            f'  {graph_node_id} [label="{label}", '
            f'fillcolor="{fill_color}"];'
        )

    for edge in relationship_graph.get("edges", []):
        source_id = node_id_by_address.get(
            edge.get("source")
        )
        target_id = node_id_by_address.get(
            edge.get("target")
        )

        if source_id is None or target_id is None:
            continue

        strength = float(
            edge.get("relationship_strength", 0.0)
            or 0.0
        )
        similarity = float(
            edge.get("behavior_similarity", 0.0)
            or 0.0
        )
        pen_width = 1.0 + (strength * 4.0)
        label = (
            f"strength {strength:.2f}\\n"
            f"similarity {similarity:.2f}"
        )
        lines.append(
            f'  {source_id} -- {target_id} '
            f'[label="{label}", penwidth="{pen_width:.2f}"];'
        )

    lines.append("}")
    return "\n".join(lines)
