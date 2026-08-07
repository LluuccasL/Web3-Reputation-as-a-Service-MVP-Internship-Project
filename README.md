# Web3 Trust API

A developer-facing proof-of-human service for Ethereum wallet reputation,
behavior analysis, Sybil detection, and privacy-safe signed proofs. The MVP
includes a FastAPI backend, deterministic demo scenarios, background scoring,
monitoring, a Streamlit dashboard, and Python and Node.js clients.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set secure local values for `API_KEYS` and `PROOF_SIGNING_SECRET` in `.env`.
Set `DEMO_MODE=true` to use synthetic wallets without live provider calls for
trust, enhanced-trust, and Sybil analysis.

Start the API:

```bash
uvicorn app.main:app --reload
```

Open the interactive API reference at
[`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs), or start the
dashboard in a second terminal:

```bash
streamlit run dashboard/app.py
```

## Developer clients

Python:

```bash
python -m pip install -e sdks/python
WEB3_TRUST_API_KEY=your-key python examples/python_quickstart.py
```

Node.js 18+:

```bash
WEB3_TRUST_API_KEY=your-key node examples/javascript_quickstart.mjs
```

The [developer integration guide](docs/developer_integration.md) covers proof
verification, Sybil analysis, background jobs, errors, and both SDKs.

## Core API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/check_wallet` | Return public trust signals |
| `POST` | `/check_wallet/enhanced` | Add behavioral and bot analysis |
| `POST` | `/generate_proof` | Generate an expiring signed proof |
| `POST` | `/verify_proof` | Verify a proof without the raw wallet |
| `POST` | `/sybil/analyze` | Analyze wallet relationships and clusters |
| `POST` | `/jobs/score-wallet` | Queue a background score |
| `GET` | `/jobs/{job_id}` | Read background-job status and result |
| `GET` | `/performance/metrics` | Read request, cache, and job metrics |
| `GET` | `/demo_wallets` | List deterministic synthetic scenarios |
| `GET` | `/version` | Read the frozen public API version |

Protected routes use the `X-API-Key` request header. Errors include a stable
code and request ID for troubleshooting.

## Tests

```bash
python -m pytest -q
cd sdks/javascript && npm test
```

The Python suite covers the API, scoring, resilience, dashboard integrations,
and Python SDK. The Node.js suite validates the JavaScript client contract.

## Project references

- [Architecture](architecture.md)
- [API requirements](api_requirements.md)
- [Python SDK](sdks/python/README.md)
- [Node.js SDK](sdks/javascript/README.md)
- [Week 7 benchmark artifacts](benchmarks/)
