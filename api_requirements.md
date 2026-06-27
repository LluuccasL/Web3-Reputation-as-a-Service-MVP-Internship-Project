**API requirements**:

Goal:
The backend should accept a wallet address, validate it, fetch basic blockchain information, and store the wallet in the database.

For Week 1:
Request:
{
  "wallet_address": "0x..."
}

Example API Response:
{
  "wallet": "0x123...",
  "human_likelihood": "high",
  "trust_tier": "silver",
  "confidence_score": 0.87,
  "risk_flags": ["low_sybil_risk"],
  "proof": {
    "issued_at": "timestamp",
    "valid_for_hours": 24
  }
}

Validation rules:
  Wallet address must start with 0x
  Wallet should not be duplicated in the database

Future endpoints
  GET /wallets/{address}
  GET /health
  POST /check_wallet
  POST /generate_proof
