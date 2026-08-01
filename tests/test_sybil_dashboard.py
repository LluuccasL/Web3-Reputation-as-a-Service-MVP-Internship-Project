import pytest

from dashboard.sybil_client import SybilAPIClient
from dashboard.sybil_view import (
    CUSTOM_DEMO_PRESET,
    INDEPENDENT_PRESET,
    SYBIL_PRESET,
    demo_addresses_for_preset,
    parse_wallet_addresses,
    relationship_edge_rows,
    relationship_graph_dot,
    wallet_result_rows,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200
        self.ok = True
        self.text = ""

    def json(self):
        return self.payload


ADDRESSES = [
    f"0x{number:040x}"
    for number in range(1, 4)
]


def _demo_wallets():
    return [
        {
            "scenario_key": "sybil_alpha",
            "address": ADDRESSES[0],
            "group_id": "demo_sybil_cluster",
        },
        {
            "scenario_key": "sybil_beta",
            "address": ADDRESSES[1],
            "group_id": "demo_sybil_cluster",
        },
        {
            "scenario_key": "established_human",
            "address": ADDRESSES[2],
            "group_id": None,
        },
        {
            "scenario_key": "normal_active",
            "address": f"0x{4:040x}",
            "group_id": None,
        },
    ]


def _analysis_result():
    return {
        "wallet_results": [
            {
                "address": ADDRESSES[0],
                "sybil_risk_score": 90,
                "sybil_risk_level": "critical",
                "cluster_id": "sybil-123456789abc",
                "related_wallets": [
                    {"address": ADDRESSES[1]}
                ],
                "risk_flags": [
                    "shared_funding_source",
                ],
            },
            {
                "address": ADDRESSES[1],
                "sybil_risk_score": 90,
                "sybil_risk_level": "critical",
                "cluster_id": "sybil-123456789abc",
                "related_wallets": [
                    {"address": ADDRESSES[0]}
                ],
                "risk_flags": [
                    "shared_funding_source",
                ],
            },
        ],
        "relationship_graph": {
            "nodes": [
                {
                    "id": ADDRESSES[0],
                    "node_type": "wallet",
                },
                {
                    "id": ADDRESSES[1],
                    "node_type": "wallet",
                },
            ],
            "edges": [
                {
                    "source": ADDRESSES[0],
                    "target": ADDRESSES[1],
                    "relationship_strength": 0.8,
                    "behavior_similarity": 1.0,
                    "matching_fingerprint": True,
                    "evidence_types": [
                        "shared_funder",
                        "coordinated_timing",
                    ],
                }
            ],
        },
    }


def test_client_posts_sybil_analysis(monkeypatch):
    client = SybilAPIClient(
        base_url="http://127.0.0.1:8000",
        api_key="test-api-key",
    )

    def fake_request(method, url, timeout, **kwargs):
        assert method == "POST"
        assert url.endswith("/sybil/analyze")

        assert kwargs["json"] == {
            "wallet_addresses": ADDRESSES[:2],
            "timing_window_seconds": 600,
        }

        return FakeResponse({"cluster_count": 1})

    monkeypatch.setattr(
        client.session,
        "request",
        fake_request,
    )

    result = client.analyze_sybil_wallets(
        ADDRESSES[:2],
        timing_window_seconds=600,
    )

    assert result["cluster_count"] == 1


def test_parses_newline_comma_and_space_addresses():
    raw_value = (
        f"{ADDRESSES[0]},\n"
        f"{ADDRESSES[1]} {ADDRESSES[2].upper()}"
    )

    assert parse_wallet_addresses(
        raw_value
    ) == ADDRESSES


@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        (
            ADDRESSES[0],
            "Enter at least two",
        ),
        (
            f"{ADDRESSES[0]}\n{ADDRESSES[0]}",
            "must not contain duplicates",
        ),
        (
            f"{ADDRESSES[0]}\nnot-a-wallet",
            "Invalid wallet address",
        ),
    ],
)
def test_rejects_invalid_manual_wallet_groups(
    raw_value,
    message,
):
    with pytest.raises(ValueError, match=message):
        parse_wallet_addresses(raw_value)


def test_resolves_demo_presets():
    demo_wallets = _demo_wallets()

    assert demo_addresses_for_preset(
        demo_wallets,
        SYBIL_PRESET,
    ) == ADDRESSES[:2]

    assert demo_addresses_for_preset(
        demo_wallets,
        INDEPENDENT_PRESET,
    ) == [
        ADDRESSES[2],
        f"0x{4:040x}",
    ]

    assert demo_addresses_for_preset(
        demo_wallets,
        CUSTOM_DEMO_PRESET,
        selected_scenario_keys=[
            "sybil_beta",
            "established_human",
        ],
    ) == [
        ADDRESSES[1],
        ADDRESSES[2],
    ]


def test_builds_wallet_result_rows():
    rows = wallet_result_rows(
        _analysis_result()["wallet_results"]
    )

    assert len(rows) == 2
    assert rows[0]["Risk Score"] == 90
    assert rows[0]["Risk Level"] == "Critical"
    assert rows[0]["Related Wallets"] == 1
    assert rows[0]["Flags"] == (
        "Shared Funding Source"
    )


def test_builds_edge_rows():
    rows = relationship_edge_rows(
        _analysis_result()["relationship_graph"]
    )

    assert len(rows) == 1
    assert rows[0]["Relationship Strength"] == 0.8
    assert rows[0]["Behavior Similarity"] == 1.0
    assert rows[0]["Evidence"] == (
        "Shared Funder, Coordinated Timing"
    )


def test_builds_graphviz_source():
    result = _analysis_result()

    dot_source = relationship_graph_dot(
        result["relationship_graph"],
        result["wallet_results"],
    )

    assert dot_source.startswith(
        "graph wallet_relationships {"
    )
    assert "wallet_0 -- wallet_1" in dot_source
    assert "Critical · 90/100" in dot_source
    assert "strength 0.80" in dot_source
    assert "similarity 1.00" in dot_source
