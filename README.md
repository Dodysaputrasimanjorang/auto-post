# Auto Discord Poster

A local-only Discord auto poster that uses a single Discord webhook:

- Single webhook integration
- Local dashboard
- Multiple auto-post jobs
- JSON-based storage
- Scheduled message delivery
- Basic activity logging

## Features implemented

- Webhook status indicator
- Create, enable, disable, and delete auto-post jobs
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
2. Fill in your Discord webhook URL
3. Install dependencies
4. Run `python app.py`

## Notes

- This is local-only and does not include login.
- Message sending only works while the webhook URL is configured.
- Data is stored in `data/automations.json`.
