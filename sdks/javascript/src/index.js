export class Web3TrustError extends Error {
  constructor(message, { statusCode = null, code = null, requestId = null } = {}) {
    super(message);
    this.name = "Web3TrustError";
    this.statusCode = statusCode;
    this.code = code;
    this.requestId = requestId;
  }
}

export class Web3TrustClient {
  constructor({ baseUrl, apiKey = "", timeoutMs = 15000, fetchImpl = fetch }) {
    let parsedUrl;

    try {
      parsedUrl = new URL(baseUrl);
    } catch {
      throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
    }

    if (!["http:", "https:"].includes(parsedUrl.protocol)) {
      throw new TypeError("baseUrl must be an absolute HTTP(S) URL");
    }

    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new TypeError("timeoutMs must be greater than zero");
    }

    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
    this.fetch = fetchImpl;
  }

  async request(method, path, { body, query } = {}) {
    const url = new URL(`${this.baseUrl}${path}`);

    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }

    const headers = { Accept: "application/json" };

    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
    }

    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;

    try {
      response = await this.fetch(url, {
        method,
        headers,
        signal: controller.signal,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (error) {
      if (error instanceof Web3TrustError) {
        throw error;
      }

      const timedOut = error?.name === "AbortError";
      throw new Web3TrustError(
        timedOut
          ? "The Web3 Trust API request timed out."
          : "Could not connect to the Web3 Trust API.",
        { code: timedOut ? "CLIENT_TIMEOUT" : "CONNECTION_ERROR" },
      );
    } finally {
      clearTimeout(timeout);
    }

    const text = await response.text();
    let data;

    try {
      data = JSON.parse(text);
    } catch {
      throw new Web3TrustError(
        "The Web3 Trust API returned an unreadable response.",
        { statusCode: response.status, code: "INVALID_RESPONSE" },
      );
    }

    if (response.ok) {
      return data;
    }

    const error = data?.error ?? {};
    throw new Web3TrustError(
      error.message ?? data?.detail ?? `API request failed with status ${response.status}.`,
      {
        statusCode: response.status,
        code: error.code ?? null,
        requestId: error.request_id ?? null,
      },
    );
  }

  version() {
    return this.request("GET", "/version");
  }

  listDemoWallets() {
    return this.request("GET", "/demo_wallets");
  }

  checkWallet(walletAddress) {
    return this.request("POST", "/check_wallet", {
      body: { wallet_address: walletAddress },
    });
  }

  checkWalletEnhanced(walletAddress) {
    return this.request("POST", "/check_wallet/enhanced", {
      body: { wallet_address: walletAddress },
    });
  }

  generateProof(walletAddress, { validForHours = 24 } = {}) {
    return this.request("POST", "/generate_proof", {
      body: {
        wallet_address: walletAddress,
        valid_for_hours: validForHours,
      },
    });
  }

  verifyProof(signedProof) {
    return this.request("POST", "/verify_proof", { body: signedProof });
  }

  analyzeSybil(walletAddresses, { timingWindowSeconds = 300 } = {}) {
    return this.request("POST", "/sybil/analyze", {
      body: {
        wallet_addresses: walletAddresses,
        timing_window_seconds: timingWindowSeconds,
      },
    });
  }

  submitScoreJob(walletAddress) {
    return this.request("POST", "/jobs/score-wallet", {
      body: { wallet_address: walletAddress },
    });
  }

  refreshScore(walletAddress) {
    return this.request(
      "POST",
      `/wallets/${encodeURIComponent(walletAddress)}/refresh-score`,
    );
  }

  getJob(jobId) {
    return this.request("GET", `/jobs/${encodeURIComponent(jobId)}`);
  }

  listJobs({ limit = 20, status } = {}) {
    return this.request("GET", "/jobs", { query: { limit, status } });
  }

  getLatestScore(walletAddress) {
    return this.request(
      "GET",
      `/wallets/${encodeURIComponent(walletAddress)}/latest-score`,
    );
  }

  getMetrics() {
    return this.request("GET", "/performance/metrics");
  }
}
