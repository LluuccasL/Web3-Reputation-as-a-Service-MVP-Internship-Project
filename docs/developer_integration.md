# Developer integration guide

This guide exercises Web3 Trust API v1 locally with deterministic synthetic
wallets. It does not require sending a real wallet to a third party.

## 1. Start the API in demo mode

Create `.env` from `.env.example`, then set:

```dotenv
API_KEYS=local-developer-key
PROOF_SIGNING_SECRET=replace-with-a-random-secret-at-least-32-characters
DEMO_MODE=true
```

Start the service:

```bash
source venv/bin/activate
uvicorn app.main:app --reload
```

Confirm the frozen public version:

```bash
curl http://127.0.0.1:8000/version
```

The OpenAPI document is available at `/openapi.json` and the interactive
reference at `/docs`.

## 2. Make a direct API request

Every analysis, proof, job, and metrics route expects `X-API-Key`:

```bash
curl --request POST http://127.0.0.1:8000/check_wallet \
  --header 'Content-Type: application/json' \
  --header 'X-API-Key: local-developer-key' \
  --data '{
    "wallet_address": "0xd000000000000000000000000000000000000001"
  }'
```

The deterministic `established_human` wallet should return strong positive
signals. Use `GET /demo_wallets` to discover normal, automated, partial-data,
and linked Sybil scenarios.

## 3. Python client

Install the local package and configure the example:

```bash
python -m pip install -e sdks/python
export WEB3_TRUST_API_KEY=local-developer-key
python examples/python_quickstart.py
```

The proof returned by `generate_proof` is already in the shape expected by
`verify_proof`:

```python
from web3_trust import TrustAPIClient

client = TrustAPIClient(
    base_url="http://127.0.0.1:8000",
    api_key="local-developer-key",
)

signed_proof = client.generate_proof(
    "0xd000000000000000000000000000000000000001"
)
verification = client.verify_proof(signed_proof)
```

## 4. Node.js client

Node.js 18 or newer is sufficient; the client has no runtime dependencies:

```bash
export WEB3_TRUST_API_KEY=local-developer-key
node examples/javascript_quickstart.mjs
```

```javascript
import { Web3TrustClient } from "./sdks/javascript/src/index.js";

const client = new Web3TrustClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: "local-developer-key",
});

const result = await client.checkWallet(
  "0xd000000000000000000000000000000000000001",
);
```

## 5. Sybil analysis

Analyze the linked synthetic wallets together so relationship evidence is
available to the clustering service:

```python
result = client.analyze_sybil(
    [
        "0xd000000000000000000000000000000000000009",
        "0xd00000000000000000000000000000000000000a",
        "0xd00000000000000000000000000000000000000b",
    ],
    timing_window_seconds=300,
)
```

Use `cluster_count`, each wallet's `sybil_risk_level`, and privacy-safe
`explanations` for product decisions. Do not treat the MVP score as identity
proof or as the sole basis for a high-impact decision.

## 6. Background scoring

```python
accepted = client.submit_score_job(
    "0xd000000000000000000000000000000000000001"
)
job = client.get_job(accepted["job_id"])
```

Submission returns HTTP 202. Poll the returned `status_url` until `status` is
`completed` or `failed`; use backoff instead of a tight loop. Equivalent active
jobs can be deduplicated.

## 7. Errors and observability

Protected API errors use this stable envelope:

```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "Invalid or missing API key.",
    "request_id": "request-correlation-id"
  },
  "detail": "Invalid or missing API key."
}
```

Both SDKs expose the status, code, and request ID on their error class. Record
the request ID in logs or support reports. Trust responses also expose cache,
processing-time, and rate-limit metadata in response headers for direct HTTP
clients.

## 8. Verify the client contract

```bash
python -m pytest -q
cd sdks/javascript
npm test
```
