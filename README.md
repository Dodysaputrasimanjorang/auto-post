# Auto Discord Poster

A local-only Discord auto poster that uses user-account HTTP API with **2 Discord accounts**:

- Dual account integration (each with its own token & login status)
- Local dashboard
- Multiple auto-post jobs assigned per account
- JSON-based storage
- Scheduled message delivery
- Basic activity logging

## Features implemented

- Account status indicator for Akun 1 & Akun 2
- Per-account token management
- Create, enable, disable, and delete auto-post jobs (assigned to an account)
- Local dashboard without login
- Automatic scheduling while the app is running
- Message delivery logs to file

## Project roadmap coverage

This starter implements the foundation for:

- Phase 1: Requirements analysis
- Phase 2: Discord integration
- Phase 3: Local dashboard
- Phase 4: Auto-post management
- Phase 5: Scheduling
- Phase 6: Monitoring
- Phase 7: Logging

## Setup

1. Copy `.env.example` to `.env`
2. Fill in `DISCORD_TOKEN` (Akun 1) and `DISCORD_TOKEN2` (Akun 2)
3. Optionally set `ACCOUNT_1_NAME` / `ACCOUNT_2_NAME` for labels
4. Install dependencies
5. Run `python app.py`

## Notes

- This is local-only and does not include login.
- Message sending only works while the respective account token is configured.
- Data is stored in `data/automations.json`.
- Saving a token via the dashboard writes it into `.env`.
