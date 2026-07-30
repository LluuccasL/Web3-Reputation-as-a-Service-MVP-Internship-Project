from copy import deepcopy
from typing import Any


def _demo_address(number: int) -> str:
    return f"0xd{number:039x}"


def _external_address(number: int) -> str:
    return f"0x{number:040x}"


DEMO_ADDRESS_BY_KEY = {
    "established_human": _demo_address(1),
    "normal_active": _demo_address(2),
    "new_wallet": _demo_address(3),
    "empty_wallet": _demo_address(4),
    "burst_bot": _demo_address(5),
    "repetitive_bot": _demo_address(6),
    "contract_heavy": _demo_address(7),
    "nft_automation": _demo_address(8),
    "sybil_alpha": _demo_address(9),
    "sybil_beta": _demo_address(10),
    "sybil_gamma": _demo_address(11),
    "partial_data_control": _demo_address(12),
}

SHARED_SYBIL_FUNDER = (
    "0xf000000000000000000000000000000000000001"
)

COMMON_SYBIL_RECIPIENTS = [
    "0xc000000000000000000000000000000000000001",
    "0xc000000000000000000000000000000000000002",
]

DEMO_CONTRACTS = [
    f"0xc{number:039x}"
    for number in range(101, 107)
]


def _transfer(
    wallet: str,
    sender: str,
    receiver: str,
    timestamp: str,
    transfer_id: int,
    category: str = "external",
    asset: str = "ETH",
) -> dict[str, Any]:
    if sender.lower() == wallet.lower():
        direction = "outgoing"
    else:
        direction = "incoming"

    return {
        "hash": f"0x{transfer_id:064x}",
        "from": sender,
        "to": receiver,
        "direction": direction,
        "category": category,
        "asset": asset,
        "value": 1.0,
        "metadata": {
            "blockTimestamp": timestamp,
        },
    }


def _outgoing_series(
    wallet: str,
    recipients: list[str],
    timestamps: list[str],
    transfer_id_start: int,
    category: str = "external",
    asset: str = "ETH",
) -> list[dict[str, Any]]:
    return [
        _transfer(
            wallet=wallet,
            sender=wallet,
            receiver=recipient,
            timestamp=timestamp,
            transfer_id=transfer_id_start + index,
            category=category,
            asset=asset,
        )
        for index, (recipient, timestamp) in enumerate(
            zip(recipients, timestamps),
            start=1,
        )
    ]


def _activity_range(
    transfers: list[dict[str, Any]],
) -> dict[str, str]:
    timestamps = [
        transfer.get("metadata", {}).get("blockTimestamp")
        for transfer in transfers
    ]

    available_timestamps = [
        timestamp
        for timestamp in timestamps
        if timestamp
    ]

    if not available_timestamps:
        return {}

    return {
        "first_activity_at": min(available_timestamps),
        "last_activity_at": max(available_timestamps),
    }


def _source_status(
    transfers: str = "available",
    nft_activity: str = "available",
    transaction_details: str = "available",
    contract_detection: str = "available",
    activity_range: str = "available",
) -> dict[str, str]:
    return {
        "balance": "available",
        "transfers": transfers,
        "nft_activity": nft_activity,
        "transaction_details": transaction_details,
        "contract_detection": contract_detection,
        "activity_range": activity_range,
    }


def _enriched_data(
    address: str,
    transfers: list[dict[str, Any]],
    nft_transfers: list[dict[str, Any]] | None = None,
    contract_addresses: list[str] | None = None,
    source_status: dict[str, str] | None = None,
    errors: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "address": address,
        "balance": "1.0",
        "transfers": transfers,
        "nft_transfers": nft_transfers or [],
        "transaction_details": [],
        "contract_addresses": contract_addresses or [],
        "activity_range": _activity_range(transfers),
        "source_status": source_status or _source_status(),
        "errors": errors or {},
    }


def _build_sybil_transfers(
    wallet: str,
    minute_offset: int,
    transfer_id_start: int,
) -> list[dict[str, Any]]:
    offset = f"{minute_offset:02d}"

    return [
        _transfer(
            wallet,
            SHARED_SYBIL_FUNDER,
            wallet,
            f"2026-06-01T12:{offset}:00Z",
            transfer_id_start + 1,
        ),
        _transfer(
            wallet,
            wallet,
            COMMON_SYBIL_RECIPIENTS[0],
            f"2026-06-01T13:{offset}:00Z",
            transfer_id_start + 2,
        ),
        _transfer(
            wallet,
            wallet,
            COMMON_SYBIL_RECIPIENTS[1],
            f"2026-06-01T13:{offset}:20Z",
            transfer_id_start + 3,
        ),
        _transfer(
            wallet,
            wallet,
            COMMON_SYBIL_RECIPIENTS[0],
            f"2026-06-02T13:{offset}:00Z",
            transfer_id_start + 4,
        ),
        _transfer(
            wallet,
            wallet,
            COMMON_SYBIL_RECIPIENTS[1],
            f"2026-06-02T13:{offset}:20Z",
            transfer_id_start + 5,
        ),
        _transfer(
            wallet,
            wallet,
            COMMON_SYBIL_RECIPIENTS[0],
            f"2026-06-03T13:{offset}:00Z",
            transfer_id_start + 6,
        ),
    ]


def _build_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    def add(
        key: str,
        label: str,
        description: str,
        expected_outcome: str,
        enriched_data: dict[str, Any],
        group_id: str | None = None,
    ) -> None:
        catalog[key] = {
            "scenario_key": key,
            "address": DEMO_ADDRESS_BY_KEY[key],
            "label": label,
            "description": description,
            "expected_outcome": expected_outcome,
            "synthetic": True,
            "group_id": group_id,
            "enriched_data": enriched_data,
        }

    established = DEMO_ADDRESS_BY_KEY["established_human"]

    established_transfers = _outgoing_series(
        established,
        [_external_address(number) for number in range(201, 209)],
        [
            "2025-01-01T12:00:00Z",
            "2025-03-10T12:00:00Z",
            "2025-05-20T12:00:00Z",
            "2025-08-15T12:00:00Z",
            "2025-11-05T12:00:00Z",
            "2026-02-14T12:00:00Z",
            "2026-04-20T12:00:00Z",
            "2026-06-30T12:00:00Z",
        ],
        100,
    )

    add(
        "established_human",
        "Established human wallet",
        "Long lifespan with varied counterparties and activity.",
        "Positive score factors and a likely Gold tier.",
        _enriched_data(established, established_transfers),
    )

    normal = DEMO_ADDRESS_BY_KEY["normal_active"]

    normal_transfers = _outgoing_series(
        normal,
        [_external_address(number) for number in range(301, 307)],
        [
            "2026-02-01T12:00:00Z",
            "2026-03-01T12:00:00Z",
            "2026-04-01T12:00:00Z",
            "2026-05-01T12:00:00Z",
            "2026-06-01T12:00:00Z",
            "2026-07-01T12:00:00Z",
        ],
        200,
    )

    add(
        "normal_active",
        "Normal active wallet",
        "Moderate activity across several independent addresses.",
        "Low or no risk with moderate positive behavior.",
        _enriched_data(normal, normal_transfers),
    )

    new_wallet = DEMO_ADDRESS_BY_KEY["new_wallet"]

    new_transfers = _outgoing_series(
        new_wallet,
        [_external_address(401), _external_address(402)],
        [
            "2026-07-28T10:00:00Z",
            "2026-07-28T18:00:00Z",
        ],
        300,
    )

    add(
        "new_wallet",
        "New wallet",
        "A very short history with only two transfers.",
        "Limited evidence and few score adjustments.",
        _enriched_data(new_wallet, new_transfers),
    )

    empty_wallet = DEMO_ADDRESS_BY_KEY["empty_wallet"]

    add(
        "empty_wallet",
        "Empty wallet",
        "No transfer, NFT, or contract activity.",
        "No behavioral evidence or risk flags.",
        _enriched_data(empty_wallet, []),
    )

    burst_bot = DEMO_ADDRESS_BY_KEY["burst_bot"]
    burst_recipient = _external_address(501)

    burst_transfers = _outgoing_series(
        burst_bot,
        [burst_recipient for _ in range(8)],
        [
            f"2026-07-01T12:00:{second:02d}Z"
            for second in range(0, 40, 5)
        ],
        400,
    )

    add(
        "burst_bot",
        "Burst-activity bot",
        "Eight repeated transfers occur within 35 seconds.",
        "High burst, repetition, and low-diversity risk.",
        _enriched_data(burst_bot, burst_transfers),
    )

    repetitive_bot = DEMO_ADDRESS_BY_KEY["repetitive_bot"]
    repeated_recipient = _external_address(601)

    repetitive_transfers = _outgoing_series(
        repetitive_bot,
        [repeated_recipient for _ in range(8)],
        [
            f"2026-06-{day:02d}T12:00:00Z"
            for day in range(1, 9)
        ],
        500,
    )

    add(
        "repetitive_bot",
        "Repetitive bot",
        "The same transaction pattern repeats across several days.",
        "Repeated-loop and low-diversity risk flags.",
        _enriched_data(repetitive_bot, repetitive_transfers),
    )

    contract_heavy = DEMO_ADDRESS_BY_KEY["contract_heavy"]

    contract_transfers = _outgoing_series(
        contract_heavy,
        DEMO_CONTRACTS[:5],
        [
            "2025-01-01T12:00:00Z",
            "2025-04-01T12:00:00Z",
            "2025-07-01T12:00:00Z",
            "2025-10-01T12:00:00Z",
            "2026-04-01T12:00:00Z",
        ],
        600,
    )

    add(
        "contract_heavy",
        "Contract-heavy wallet",
        "All transfers use different known contracts.",
        "Informational contract usage without bot risk.",
        _enriched_data(
            contract_heavy,
            contract_transfers,
            contract_addresses=DEMO_CONTRACTS[:5],
        ),
    )

    nft_wallet = DEMO_ADDRESS_BY_KEY["nft_automation"]
    nft_contract = DEMO_CONTRACTS[5]

    nft_transfers = _outgoing_series(
        nft_wallet,
        [nft_contract for _ in range(12)],
        [
            f"2026-07-10T12:{minute:02d}:00Z"
            for minute in range(12)
        ],
        700,
        category="erc721",
        asset="DEMO-NFT",
    )

    add(
        "nft_automation",
        "NFT automation wallet",
        "Twelve repetitive NFT transfers target one contract.",
        "NFT automation and repetitive-behavior risk.",
        _enriched_data(
            nft_wallet,
            nft_transfers,
            nft_transfers=deepcopy(nft_transfers),
            contract_addresses=[nft_contract],
        ),
    )

    for index, key in enumerate(
        ["sybil_alpha", "sybil_beta", "sybil_gamma"],
        start=1,
    ):
        wallet = DEMO_ADDRESS_BY_KEY[key]

        sybil_transfers = _build_sybil_transfers(
            wallet,
            minute_offset=index,
            transfer_id_start=800 + (index * 10),
        )

        add(
            key,
            f"Sybil cluster wallet {index}",
            (
                "Shares a funder, recipients, timing, and behavior "
                "with two related demo wallets."
            ),
            "Expected to join the synthetic Sybil cluster.",
            _enriched_data(wallet, sybil_transfers),
            group_id="demo_sybil_cluster",
        )

    partial_wallet = DEMO_ADDRESS_BY_KEY[
        "partial_data_control"
    ]

    partial_transfers = _outgoing_series(
        partial_wallet,
        [
            _external_address(901),
            _external_address(902),
            _external_address(903),
            _external_address(904),
        ],
        [
            "2026-01-01T12:00:00Z",
            "2026-02-01T12:00:00Z",
            "2026-03-01T12:00:00Z",
            "2026-04-01T12:00:00Z",
        ],
        900,
    )

    add(
        "partial_data_control",
        "Partial-data independent wallet",
        (
            "An independent control wallet with unavailable "
            "NFT and transaction-detail sources."
        ),
        "Reduced data coverage without joining the Sybil cluster.",
        _enriched_data(
            partial_wallet,
            partial_transfers,
            source_status=_source_status(
                transfers="partial",
                nft_activity="unavailable",
                transaction_details="unavailable",
            ),
            errors={
                "transfers": (
                    "Only part of the synthetic transfer history "
                    "is available."
                ),
                "nft_activity": (
                    "Synthetic NFT source is unavailable."
                ),
                "transaction_details": (
                    "Synthetic transaction details are unavailable."
                ),
            },
        ),
    )

    return catalog


DEMO_BALANCE_BY_KEY = {
    "established_human": "1.0",
    "normal_active": "0.001",
    "new_wallet": "0",
    "empty_wallet": "0",
    "burst_bot": "0",
    "repetitive_bot": "0",
    "contract_heavy": "0.01",
    "nft_automation": "0",
    "sybil_alpha": "0.001",
    "sybil_beta": "0.001",
    "sybil_gamma": "0.001",
    "partial_data_control": "0.001",
}


DEMO_WALLETS = _build_catalog()


def list_demo_wallets() -> list[dict[str, Any]]:
    return [
        {
            key: deepcopy(value)
            for key, value in wallet.items()
            if key != "enriched_data"
        }
        for wallet in DEMO_WALLETS.values()
    ]


def is_demo_wallet(address: str) -> bool:
    normalized_address = address.lower()

    return any(
        wallet["address"] == normalized_address
        for wallet in DEMO_WALLETS.values()
    )


def get_demo_wallet(
    address: str,
) -> dict[str, Any] | None:
    normalized_address = address.lower()

    for wallet in DEMO_WALLETS.values():
        if wallet["address"] == normalized_address:
            return deepcopy(wallet)

    return None


def get_demo_enriched_data(
    address: str,
) -> dict[str, Any] | None:
    wallet = get_demo_wallet(address)

    if wallet is None:
        return None

    enriched_data = wallet["enriched_data"]
    enriched_data["balance"] = DEMO_BALANCE_BY_KEY[
        wallet["scenario_key"]
    ]
    enriched_data["is_demo"] = True
    enriched_data["demo_scenario"] = wallet["scenario_key"]
    enriched_data["demo_label"] = wallet["label"]

    return enriched_data
