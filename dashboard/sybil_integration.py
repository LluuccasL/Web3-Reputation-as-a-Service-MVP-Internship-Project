import re
from typing import Any


WALLET_ADDRESS_PATTERN = re.compile(
    r"^0x[a-fA-F0-9]{40}$"
)


def stored_wallet_addresses(
    wallet_results: list[dict[str, Any]],
) -> list[str]:
    """
    Return normalized, unique addresses that are safe for batch analysis.
    """
    addresses: list[str] = []
    seen: set[str] = set()

    for result in wallet_results:
        raw_address = (
            result.get("wallet_address")
            or result.get("address")
        )

        if not isinstance(raw_address, str):
            continue

        address = raw_address.strip().lower()

        if not WALLET_ADDRESS_PATTERN.fullmatch(address):
            raise ValueError(
                f"Invalid stored wallet address: {raw_address}"
            )

        if address in seen:
            continue

        seen.add(address)
        addresses.append(address)

    if len(addresses) > 25:
        raise ValueError(
            "Sybil analysis supports no more than 25 stored wallets "
            "at one time."
        )

    return addresses


def sybil_results_by_address(
    sybil_analysis: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(sybil_analysis, dict):
        return {}

    return {
        str(result["address"]).lower(): result
        for result in sybil_analysis.get(
            "wallet_results",
            [],
        )
        if isinstance(result, dict)
        and result.get("address")
    }


def sybil_context_for_wallet(
    sybil_analysis: dict[str, Any] | None,
    wallet_address: str | None,
) -> dict[str, Any] | None:
    if not wallet_address:
        return None

    return sybil_results_by_address(
        sybil_analysis
    ).get(wallet_address.strip().lower())


def merge_trust_and_sybil_results(
    trust_results: list[dict[str, Any]],
    sybil_analysis: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Add batch Sybil context while preserving each original trust result.
    """
    sybil_by_address = sybil_results_by_address(
        sybil_analysis
    )
    merged_results: list[dict[str, Any]] = []

    for trust_result in trust_results:
        address = str(
            trust_result.get("wallet_address")
            or trust_result.get("address")
            or ""
        ).lower()
        sybil_result = sybil_by_address.get(
            address,
            {},
        )

        merged_results.append(
            {
                **trust_result,
                "sybil_risk_score": int(
                    sybil_result.get(
                        "sybil_risk_score",
                        0,
                    )
                    or 0
                ),
                "sybil_risk_level": str(
                    sybil_result.get(
                        "sybil_risk_level",
                        "low",
                    )
                ),
                "sybil_cluster_id": sybil_result.get(
                    "cluster_id"
                ),
                "sybil_cluster_size": int(
                    sybil_result.get(
                        "cluster_size",
                        1,
                    )
                    or 1
                ),
                "sybil_related_wallet_count": len(
                    sybil_result.get(
                        "related_wallets",
                        [],
                    )
                ),
                "sybil_risk_flags": list(
                    sybil_result.get(
                        "risk_flags",
                        [],
                    )
                ),
            }
        )

    return merged_results


def is_flagged_wallet(
    result: dict[str, Any],
) -> bool:
    trust_tier = str(
        result.get("trust_tier", "")
    ).lower()
    human_likelihood = str(
        result.get("human_likelihood", "")
    ).lower()

    return (
        bool(result.get("risk_flags"))
        or trust_tier in {
            "bronze",
            "low",
            "untrusted",
        }
        or human_likelihood == "low"
        or bool(result.get("sybil_cluster_id"))
        or bool(result.get("sybil_risk_flags"))
    )


def flagged_wallet_rows(
    analytics_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for result in analytics_results:
        if not is_flagged_wallet(result):
            continue

        trust_flags = [
            str(flag).replace("_", " ").title()
            for flag in result.get(
                "risk_flags",
                [],
            )
        ]
        sybil_flags = [
            f"Sybil: {str(flag).replace('_', ' ').title()}"
            for flag in result.get(
                "sybil_risk_flags",
                [],
            )
        ]
        combined_flags = trust_flags + sybil_flags

        if (
            result.get("sybil_cluster_id")
            and not sybil_flags
        ):
            combined_flags.append(
                "Sybil: Cluster Membership"
            )

        rows.append(
            {
                "wallet_address": result.get(
                    "wallet_address",
                    result.get("address", ""),
                ),
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
                "sybil_risk_score": result.get(
                    "sybil_risk_score",
                    0,
                ),
                "sybil_risk_level": result.get(
                    "sybil_risk_level",
                    "low",
                ),
                "sybil_cluster": (
                    result.get("sybil_cluster_id")
                    or "Not clustered"
                ),
                "related_wallets": result.get(
                    "sybil_related_wallet_count",
                    0,
                ),
                "risk_flags": (
                    ", ".join(combined_flags)
                    or "Low trust result"
                ),
            }
        )

    return rows
