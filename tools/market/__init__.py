"""The price collector: runs in GitHub Actions, never in the app (docs/proposals/market_data.md).

    python -m tools.market collect --folder market            # today's prices from every source
    python -m tools.market backfill --folder market EG:COMI   # whole history for some instruments

Each source is an adapter in tools/market/sources with pure parse functions tested on recorded samples
(tests/fixtures/market). A run checks every answer before it reaches the file and keeps the last good
price when a source fails; health.json says what happened.
"""
