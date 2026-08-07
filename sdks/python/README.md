# Web3 Trust Python SDK

Install the local SDK from the project root:

```bash
python -m pip install -e sdks/python
```

```python
from web3_trust import TrustAPIClient

with TrustAPIClient(
    base_url="http://127.0.0.1:8000",
    api_key="your-developer-key",
) as client:
    result = client.check_wallet(
        "0xd000000000000000000000000000000000000001"
    )
    print(result["trust_tier"])
```

See [`docs/developer_integration.md`](../../docs/developer_integration.md)
for the complete local workflow.
