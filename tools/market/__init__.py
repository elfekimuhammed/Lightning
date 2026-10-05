"""The price collector: runs in GitHub Actions, never in the app (docs/proposals/market_data.md).

    python -m tools.market collect --root market --packs egx,fx   # today's prices, one folder per pack
    python -m tools.market backfill --root market EG:COMI         # whole history for some instruments
    python -m tools.market pack --root market --out market.zip    # the default packs, for a release

Packs and their schedules are in lightning/market/packs.py. Each source is an adapter in
tools/market/sources with pure parse functions tested on recorded samples (tests/fixtures/market). A run
checks every answer before it reaches the file and keeps the last good price when a source fails; each
pack's health.json says what happened, and index.json describes every pack.
"""
