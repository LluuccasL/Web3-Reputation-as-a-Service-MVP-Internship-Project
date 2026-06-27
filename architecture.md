**Architecture**:

The system is API-first. An external app sends a wallet address to the backend. The backend validates the wallet address, calls a blockchain API such as Alchemy or Etherscan, stores the wallet and metadata in Postgres/Supabase, and returns a simple response.

Main components:
1. FastAPI backend
2. Wallet ingestion service
3. Blockchain API client
4. Postgres/Supabase database
5. Future scoring service
6. Future proof generator

External App / Developer
        |
        v
FastAPI Backend
        |
        |--- Wallet Ingestion Service
        |--- Blockchain API Client
        |--- Database Service
        |
        v
Postgres/Supabase Database

