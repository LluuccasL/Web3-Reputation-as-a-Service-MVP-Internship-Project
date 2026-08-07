# Web3 Trust Node.js SDK

The client uses the `fetch` implementation built into Node.js 18 and later,
so it has no runtime dependencies.

```javascript
import { Web3TrustClient } from "./sdks/javascript/src/index.js";

const client = new Web3TrustClient({
  baseUrl: "http://127.0.0.1:8000",
  apiKey: "your-developer-key",
});

const result = await client.checkWallet(
  "0xd000000000000000000000000000000000000001",
);

console.log(result.trust_tier);
```

See [`docs/developer_integration.md`](../../docs/developer_integration.md)
for the complete local workflow.
