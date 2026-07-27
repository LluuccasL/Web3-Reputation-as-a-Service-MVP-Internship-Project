from app.services import blockchain
from app.services.enrichment import enrich_wallet


ADDRESS = "0x1111111111111111111111111111111111111111"
CONTRACT = "0x2222222222222222222222222222222222222222"
TX_HASH = "0xabc123"


def test_enrich_wallet_combines_available_data(monkeypatch):
    monkeypatch.setattr(
        blockchain,
        "get_wallet_balance",
        lambda address: {
            "address": address,
            "balance_wei": "100",
            "balance_eth": "0.0000000000000001",
            "network": "eth-mainnet",
        },
    )
    monkeypatch.setattr(
        blockchain,
        "get_asset_transfers_for_wallet",
        lambda address, max_count: [
            {
                "hash": TX_HASH,
                "to": CONTRACT,
                "category": "external",
            }
        ],
    )
    monkeypatch.setattr(
        blockchain,
        "get_nft_transfers_for_wallet",
        lambda address, max_count: [{"category": "erc721"}],
    )
    monkeypatch.setattr(
        blockchain,
        "get_wallet_activity_range",
        lambda address: {
            "first_activity_at": "2025-01-01T00:00:00Z",
            "last_activity_at": "2026-01-01T00:00:00Z",
        },
    )
    monkeypatch.setattr(
        blockchain,
        "get_transaction_by_hash",
        lambda tx_hash: {
            "hash": tx_hash,
            "to": CONTRACT,
        },
    )
    monkeypatch.setattr(
        blockchain,
        "is_contract_address",
        lambda address: address == CONTRACT,
    )

    result = enrich_wallet(ADDRESS)

    assert result["address"] == ADDRESS
    assert len(result["transfers"]) == 1
    assert len(result["nft_transfers"]) == 1
    assert len(result["transaction_details"]) == 1
    assert result["contract_addresses"] == [CONTRACT]
    assert result["errors"] == {}

    assert all(
        status == "available"
        for status in result["source_status"].values()
    )


def test_enrich_wallet_keeps_partial_results(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        blockchain,
        "get_wallet_balance",
        unavailable,
    )
    monkeypatch.setattr(
        blockchain,
        "get_asset_transfers_for_wallet",
        lambda address, max_count: [
            {
                "hash": TX_HASH,
                "to": CONTRACT,
                "category": "external",
            }
        ],
    )
    monkeypatch.setattr(
        blockchain,
        "get_nft_transfers_for_wallet",
        unavailable,
    )
    monkeypatch.setattr(
        blockchain,
        "get_wallet_activity_range",
        unavailable,
    )
    monkeypatch.setattr(
        blockchain,
        "get_transaction_by_hash",
        unavailable,
    )
    monkeypatch.setattr(
        blockchain,
        "is_contract_address",
        unavailable,
    )

    result = enrich_wallet(ADDRESS)

    assert len(result["transfers"]) == 1
    assert result["balance"] is None
    assert result["nft_transfers"] == []
    assert result["transaction_details"] == []
    assert result["contract_addresses"] == []

    assert result["source_status"]["transfers"] == "available"
    assert result["source_status"]["balance"] == "unavailable"
    assert result["source_status"]["nft_activity"] == "unavailable"
    assert result["source_status"]["activity_range"] == "unavailable"
    assert result["source_status"]["transaction_details"] == "unavailable"
    assert result["source_status"]["contract_lookup"] == "unavailable"
