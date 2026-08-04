import os

import streamlit as st
from dotenv import load_dotenv

from dashboard.api_client import (
    DashboardAPIError,
    TrustAPIClient,
)
from dashboard.operations_view import (
    active_job_count,
    job_rows,
    route_rows,
    terminal_job_rows,
)


load_dotenv()

API_BASE_URL = os.getenv(
    "DASHBOARD_API_URL",
    "http://127.0.0.1:8000",
)
API_KEY = os.getenv(
    "DASHBOARD_API_KEY",
    "",
)

st.set_page_config(
    page_title="Operations",
    page_icon="📊",
    layout="wide",
)

client = TrustAPIClient(
    base_url=API_BASE_URL,
    api_key=API_KEY,
)

st.title("Operations")
st.caption(
    "Monitor API performance, cache behavior, "
    "and background wallet-scoring jobs."
)

with st.sidebar:
    st.header("Operations Settings")
    st.text(f"API: {API_BASE_URL}")

    if API_KEY:
        st.success("API key configured")
    else:
        st.warning(
            "Dashboard API key is missing"
        )

    status_filter_label = st.selectbox(
        "Job status",
        options=[
            "All",
            "Queued",
            "Running",
            "Completed",
            "Failed",
        ],
    )

    job_limit = st.slider(
        "Jobs to display",
        min_value=5,
        max_value=100,
        value=20,
        step=5,
    )

    auto_refresh = st.toggle(
        "Auto-refresh",
        value=True,
        help=(
            "Refresh operations data every "
            "two seconds."
        ),
    )

    if st.button(
        "Refresh now",
        use_container_width=True,
    ):
        st.rerun()

st.subheader("Manual Wallet Refresh")

with st.form("manual_wallet_refresh"):
    wallet_address = st.text_input(
        "Wallet address",
        placeholder="0x...",
        help=(
            "Queue a background job that "
            "recalculates this wallet's score."
        ),
    )

    refresh_submitted = (
        st.form_submit_button(
            "Queue Score Refresh"
        )
    )

if refresh_submitted:
    if not API_KEY:
        st.error(
            "Configure DASHBOARD_API_KEY "
            "before submitting a job."
        )
    elif not wallet_address.strip():
        st.warning(
            "Enter a wallet address."
        )
    else:
        try:
            accepted_job = (
                client.refresh_wallet_score(
                    wallet_address.strip()
                )
            )

            st.success(
                "Refresh job queued: "
                f"{accepted_job.get('job_id')}"
            )
            st.session_state[
                "operations_job_id"
            ] = accepted_job.get("job_id")

        except DashboardAPIError as exc:
            st.error(exc.message)

status_filter = (
    None
    if status_filter_label == "All"
    else status_filter_label.lower()
)

refresh_interval = (
    "2s"
    if auto_refresh
    else None
)


@st.fragment(
    run_every=refresh_interval
)
def render_operations():
    try:
        health = client.health()
        metrics = (
            client.get_monitoring_metrics()
        )
        jobs_payload = client.list_jobs(
            limit=job_limit,
            status=status_filter,
        )
    except DashboardAPIError as exc:
        st.error(exc.message)
        st.info(
            "Confirm that Uvicorn is running "
            "and the dashboard API key is valid."
        )
        return

    jobs = jobs_payload.get(
        "jobs",
        [],
    )
    request_metrics = metrics.get(
        "requests",
        {},
    )
    cache_metrics = metrics.get(
        "cache",
        {},
    )
    background_jobs = metrics.get(
        "background_jobs",
        {},
    )

    st.subheader("System Health")

    (
        health_column,
        request_column,
        latency_column,
        cache_column,
    ) = st.columns(4)

    with health_column:
        is_healthy = (
            health.get("status")
            == "healthy"
        )

        st.metric(
            "API Status",
            (
                "Online"
                if is_healthy
                else "Degraded"
            ),
        )

    with request_column:
        st.metric(
            "Total Requests",
            request_metrics.get(
                "total_requests",
                0,
            ),
        )

    with latency_column:
        st.metric(
            "Average Latency",
            (
                f"{request_metrics.get(
                    'average_latency_ms',
                    0,
                ):.2f} ms"
            ),
        )

    with cache_column:
        hit_rate = cache_metrics.get(
            "hit_rate",
            0,
        )

        st.metric(
            "Cache Hit Rate",
            f"{hit_rate:.1%}",
        )

    (
        cache_size_column,
        active_request_column,
        request_error_column,
        uptime_column,
    ) = st.columns(4)

    with cache_size_column:
        st.metric(
            "Cached Scores",
            (
                f"{cache_metrics.get('size', 0)}"
                f"/{cache_metrics.get(
                    'max_size',
                    0,
                )}"
            ),
        )

    with active_request_column:
        st.metric(
            "Active Requests",
            request_metrics.get(
                "active_requests",
                0,
            ),
        )

    with request_error_column:
        st.metric(
            "Request Errors",
            request_metrics.get(
                "errors",
                0,
            ),
        )

    with uptime_column:
        st.metric(
            "Uptime",
            (
                f"{metrics.get(
                    'uptime_seconds',
                    0,
                ):.0f} seconds"
            ),
        )

    st.subheader("Background Jobs")

    (
        queued_column,
        running_column,
        completed_column,
        failed_column,
    ) = st.columns(4)

    with queued_column:
        st.metric(
            "Queued",
            background_jobs.get(
                "queued",
                0,
            ),
        )

    with running_column:
        st.metric(
            "Running",
            background_jobs.get(
                "running",
                0,
            ),
        )

    with completed_column:
        st.metric(
            "Completed",
            background_jobs.get(
                "completed",
                0,
            ),
        )

    with failed_column:
        st.metric(
            "Failed",
            background_jobs.get(
                "failed",
                0,
            ),
        )

    active_jobs = active_job_count(jobs)

    if active_jobs:
        st.info(
            f"{active_jobs} displayed job(s) "
            "are queued or running."
        )
    elif auto_refresh:
        st.caption(
            "Auto-refresh is enabled. "
            "No displayed jobs are currently active."
        )

    st.markdown("#### Recent Jobs")

    if jobs:
        st.dataframe(
            job_rows(jobs),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info(
            "No jobs match the selected filter."
        )

    completed_or_failed = (
        terminal_job_rows(jobs)
    )

    st.markdown(
        "#### Recent Completed or Failed Jobs"
    )

    if completed_or_failed:
        st.dataframe(
            completed_or_failed,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info(
            "No completed or failed jobs "
            "are currently displayed."
        )

    st.subheader("Route Performance")

    routes = route_rows(metrics)

    if routes:
        st.dataframe(
            routes,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info(
            "No route metrics have been "
            "recorded yet."
        )

    with st.expander(
        "Cache Details"
    ):
        st.json(cache_metrics)


render_operations()
