from typing import Any


JOB_STATUSES = (
    "queued",
    "running",
    "completed",
    "failed",
)


def job_status_counts(
    jobs: list[dict[str, Any]],
) -> dict[str, int]:
    counts = {
        status: 0
        for status in JOB_STATUSES
    }

    for job in jobs:
        status = str(
            job.get("status", "")
        ).lower()

        if status in counts:
            counts[status] += 1

    return counts


def active_job_count(
    jobs: list[dict[str, Any]],
) -> int:
    return sum(
        1
        for job in jobs
        if job.get("status")
        in {"queued", "running"}
    )


def job_rows(
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for job in jobs:
        rows.append(
            {
                "Job ID": job.get("id", ""),
                "Wallet": job.get(
                    "wallet_address",
                    "",
                ),
                "Type": str(
                    job.get(
                        "job_type",
                        "unknown",
                    )
                )
                .replace("_", " ")
                .title(),
                "Status": str(
                    job.get(
                        "status",
                        "unknown",
                    )
                ).title(),
                "Attempts": job.get(
                    "attempts",
                    0,
                ),
                "Created": job.get(
                    "created_at",
                    "",
                ),
                "Completed": job.get(
                    "completed_at",
                    "",
                )
                or "",
                "Error": job.get(
                    "error",
                    "",
                )
                or "",
            }
        )

    return rows


def terminal_job_rows(
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    terminal_jobs = [
        job
        for job in jobs
        if job.get("status")
        in {"completed", "failed"}
    ]

    return job_rows(terminal_jobs)


def route_rows(
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    requests = metrics.get(
        "requests",
        {},
    )
    routes = requests.get(
        "routes",
        [],
    )

    return [
        {
            "Method": route.get(
                "method",
                "",
            ),
            "Route": route.get(
                "path",
                "",
            ),
            "Requests": route.get(
                "requests",
                0,
            ),
            "Errors": route.get(
                "errors",
                0,
            ),
            "Average Latency (ms)": (
                route.get(
                    "average_latency_ms",
                    0,
                )
            ),
            "Maximum Latency (ms)": (
                route.get(
                    "max_latency_ms",
                    0,
                )
            ),
        }
        for route in routes
    ]
