"""Measure baseline latency for the Web3 Trust API."""

import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


def demo_address(number: int) -> str:
    return f"0xd{number:039x}"


def endpoint_cases() -> list[dict]:
    return [
        {
            "name": "wallet_reputation",
            "method": "GET",
            "path": (
                f"/wallets/{demo_address(1)}/reputation"
                "?max_count=10"
            ),
            "body": None,
        },
        {
            "name": "check_wallet",
            "method": "POST",
            "path": "/check_wallet",
            "body": {"wallet_address": demo_address(2)},
        },
        {
            "name": "generate_proof",
            "method": "POST",
            "path": "/generate_proof",
            "body": {
                "wallet_address": demo_address(3),
                "valid_for_hours": 24,
            },
        },
        {
            "name": "enhanced_trust",
            "method": "POST",
            "path": "/check_wallet/enhanced",
            "body": {"wallet_address": demo_address(5)},
        },
        {
            "name": "sybil_analysis",
            "method": "POST",
            "path": "/sybil/analyze",
            "body": {
                "wallet_addresses": [
                    demo_address(9),
                    demo_address(10),
                    demo_address(11),
                ],
                "timing_window_seconds": 300,
            },
        },
    ]


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        raise ValueError(
            "Cannot calculate a percentile without values"
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * percentage
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    fraction = position - lower_index

    return (
        ordered[lower_index]
        + (
            ordered[upper_index]
            - ordered[lower_index]
        )
        * fraction
    )


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "min": round(min(values), 3),
        "average": round(statistics.fmean(values), 3),
        "p50": round(percentile(values, 0.50), 3),
        "p95": round(percentile(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def get_api_key(explicit_key: str | None) -> str:
    if explicit_key:
        return explicit_key

    benchmark_key = os.getenv(
        "BENCHMARK_API_KEY",
        "",
    ).strip()

    if benchmark_key:
        return benchmark_key

    api_key = (
        os.getenv("API_KEYS", "")
        .split(",", 1)[0]
        .strip()
    )

    if not api_key:
        raise ValueError(
            "No API key found. "
            "Export API_KEYS or use --api-key."
        )

    return api_key


def timed_request(
    base_url: str,
    case: dict,
    api_key: str,
    timeout: float,
) -> float:
    started = time.perf_counter()

    try:
        response = requests.request(
            method=case["method"],
            url=(
                f"{base_url.rstrip('/')}"
                f"{case['path']}"
            ),
            headers={"X-API-Key": api_key},
            json=case["body"],
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Could not reach {base_url}: {exc}"
        ) from exc

    elapsed_ms = round(
        (time.perf_counter() - started) * 1000,
        3,
    )

    if not response.ok:
        raise RuntimeError(
            f"{case['name']} returned HTTP "
            f"{response.status_code}: {response.text}"
        )

    return elapsed_ms


def benchmark_case(
    base_url: str,
    case: dict,
    api_key: str,
    runs: int,
    timeout: float,
) -> dict:
    first_ms = timed_request(
        base_url,
        case,
        api_key,
        timeout,
    )

    repeated_ms = [
        timed_request(
            base_url,
            case,
            api_key,
            timeout,
        )
        for _ in range(runs)
    ]

    summary = summarize(repeated_ms)

    improvement_percent = 0.0

    if first_ms > 0:
        improvement_percent = (
            (
                first_ms
                - summary["average"]
            )
            / first_ms
        ) * 100

    return {
        "name": case["name"],
        "method": case["method"],
        "path": case["path"],
        "first_request_ms": first_ms,
        "repeated_request_ms": repeated_ms,
        "repeated_summary_ms": summary,
        "improvement_percent": round(
            improvement_percent,
            2,
        ),
    }


def save_results(
    results: dict,
    json_path: Path,
    csv_path: Path,
):
    json_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path.write_text(
        json.dumps(results, indent=2) + "\n",
        encoding="utf-8",
    )

    columns = [
        "name",
        "method",
        "path",
        "first_ms",
        "repeat_min_ms",
        "repeat_average_ms",
        "repeat_p50_ms",
        "repeat_p95_ms",
        "repeat_max_ms",
        "improvement_percent",
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
        )

        writer.writeheader()

        for endpoint in results["endpoints"]:
            summary = endpoint[
                "repeated_summary_ms"
            ]

            writer.writerow(
                {
                    "name": endpoint["name"],
                    "method": endpoint["method"],
                    "path": endpoint["path"],
                    "first_ms": endpoint[
                        "first_request_ms"
                    ],
                    "repeat_min_ms": summary["min"],
                    "repeat_average_ms": summary[
                        "average"
                    ],
                    "repeat_p50_ms": summary["p50"],
                    "repeat_p95_ms": summary["p95"],
                    "repeat_max_ms": summary["max"],
                    "improvement_percent": endpoint[
                        "improvement_percent"
                    ],
                }
            )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark important Web3 Trust API "
            "endpoints."
        )
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument("--api-key")

    parser.add_argument(
        "--runs",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
    )

    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(
            "benchmarks/week7_baseline.json"
        ),
    )

    parser.add_argument(
        "--csv-output",
        type=Path,
        default=Path(
            "benchmarks/week7_baseline.csv"
        ),
    )

    args = parser.parse_args()

    if args.runs < 1:
        parser.error(
            "--runs must be at least 1"
        )

    if args.timeout <= 0:
        parser.error(
            "--timeout must be greater than 0"
        )

    return args


def main() -> int:
    args = parse_args()

    try:
        api_key = get_api_key(args.api_key)
        endpoint_results = []

        for case in endpoint_cases():
            print(
                f"Benchmarking {case['name']} ...",
                flush=True,
            )

            result = benchmark_case(
                args.base_url,
                case,
                api_key,
                args.runs,
                args.timeout,
            )

            endpoint_results.append(result)

            summary = result[
                "repeated_summary_ms"
            ]

            print(
                f"  first="
                f"{result['first_request_ms']:.3f} ms, "
                f"average="
                f"{summary['average']:.3f} ms, "
                f"p95={summary['p95']:.3f} ms"
            )

        results = {
            "benchmark": "week7_baseline",
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "base_url": args.base_url,
            "repeated_runs_per_endpoint": (
                args.runs
            ),
            "endpoints": endpoint_results,
        }

        save_results(
            results,
            args.json_output,
            args.csv_output,
        )

    except (RuntimeError, ValueError) as exc:
        print(
            f"Benchmark failed: {exc}",
            file=sys.stderr,
        )

        return 1

    print(
        f"JSON results: {args.json_output}"
    )

    print(
        f"CSV results:  {args.csv_output}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
