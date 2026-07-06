# Web3-Reputation-as-a-Service-MVP-Internship-Project
8-week SDE Internship
Web3 Reputation-as-a-Service MVP – Proof-of-Human Trust API

Project Statement: https://docs.google.com/document/d/1PozsOdBivic0AkkEaL29CfGdIZObxNoB5wLLwMDsTtU/edit?usp=sharing

Weekly Snippet: https://docs.google.com/document/d/113rD1B9-Q1gl9WnXmVHvNn9n_z5-G-lt/edit?usp=sharing&ouid=109668476696236148759&rtpof=true&sd=true

## Week 2 Backend Upgrades:

Added features:
- Kept existing root route and chain latest-block route
- Kept existing wallet ingest route
- Added wallet listing, lookup, and delete endpoints
- Added wallet balance lookup using Alchemy
- Added wallet transfer lookup using Alchemy
- Added wallet reputation scoring endpoint
- Added safer error handling for Alchemy rate limits
- Prevented API key leaks in error responses
- Added automated tests with mocked Alchemy calls
- Added a temporary test database so tests do not affect local development data

## Run locally:

pip install -r requirements.txt

uvicorn app.main:app --reload
