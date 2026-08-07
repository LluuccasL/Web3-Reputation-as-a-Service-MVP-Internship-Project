import assert from "node:assert/strict";
import test from "node:test";

import { Web3TrustClient, Web3TrustError } from "../src/index.js";


function jsonResponse(payload, { status = 200, ok = true } = {}) {
  return {
    status,
    ok,
    async text() {
      return JSON.stringify(payload);
    },
  };
}


test("checkWallet sends authentication and the v1 request body", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return jsonResponse({ trust_tier: "gold" });
  };
  const client = new Web3TrustClient({
    baseUrl: "http://127.0.0.1:8000/",
    apiKey: "developer-key",
    fetchImpl,
  });
  const address = "0x1111111111111111111111111111111111111111";

  const result = await client.checkWallet(address);

  assert.equal(result.trust_tier, "gold");
  assert.equal(calls[0].url.toString(), "http://127.0.0.1:8000/check_wallet");
  assert.equal(calls[0].options.headers["X-API-Key"], "developer-key");
  assert.deepEqual(JSON.parse(calls[0].options.body), {
    wallet_address: address,
  });
});


test("generateProof output can be passed directly to verifyProof", async () => {
  const signedProof = {
    proof: { proof_id: "proof-id" },
    signature: "a".repeat(64),
  };
  const calls = [];
  const client = new Web3TrustClient({
    baseUrl: "http://localhost:8000",
    apiKey: "developer-key",
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      return jsonResponse(signedProof);
    },
  });

  const generated = await client.generateProof("0x" + "2".repeat(40), {
    validForHours: 48,
  });
  await client.verifyProof(generated);

  assert.deepEqual(JSON.parse(calls[0].options.body), {
    wallet_address: "0x" + "2".repeat(40),
    valid_for_hours: 48,
  });
  assert.equal(calls[1].url.pathname, "/verify_proof");
  assert.deepEqual(JSON.parse(calls[1].options.body), signedProof);
});


test("analyzeSybil maps JavaScript options to the API contract", async () => {
  let requestBody;
  const addresses = ["0x" + "3".repeat(40), "0x" + "4".repeat(40)];
  const client = new Web3TrustClient({
    baseUrl: "http://localhost:8000",
    apiKey: "developer-key",
    fetchImpl: async (_url, options) => {
      requestBody = JSON.parse(options.body);
      return jsonResponse({ cluster_count: 1 });
    },
  });

  await client.analyzeSybil(addresses, { timingWindowSeconds: 600 });

  assert.deepEqual(requestBody, {
    wallet_addresses: addresses,
    timing_window_seconds: 600,
  });
});


test("listJobs omits an undefined status query", async () => {
  let requestedUrl;
  const client = new Web3TrustClient({
    baseUrl: "http://localhost:8000",
    apiKey: "developer-key",
    fetchImpl: async (url) => {
      requestedUrl = url;
      return jsonResponse({ count: 0, jobs: [] });
    },
  });

  await client.listJobs({ limit: 5 });

  assert.equal(requestedUrl.search, "?limit=5");
});


test("structured API errors preserve status, code, and request ID", async () => {
  const client = new Web3TrustClient({
    baseUrl: "http://localhost:8000",
    apiKey: "invalid-key",
    fetchImpl: async () => jsonResponse(
      {
        error: {
          code: "INVALID_API_KEY",
          message: "Invalid or missing API key.",
          request_id: "request-123",
        },
      },
      { status: 401, ok: false },
    ),
  });

  await assert.rejects(
    client.getMetrics(),
    (error) => {
      assert.ok(error instanceof Web3TrustError);
      assert.equal(error.statusCode, 401);
      assert.equal(error.code, "INVALID_API_KEY");
      assert.equal(error.requestId, "request-123");
      return true;
    },
  );
});


test("invalid configuration is rejected before a request", () => {
  assert.throws(
    () => new Web3TrustClient({ baseUrl: "localhost:8000" }),
    /absolute HTTP/,
  );
  assert.throws(
    () => new Web3TrustClient({
      baseUrl: "http://localhost:8000",
      timeoutMs: 0,
    }),
    /greater than zero/,
  );
});
