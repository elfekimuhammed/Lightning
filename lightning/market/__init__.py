"""Market data shared by the app and the price collector: ISO names and the one market file.

docs/proposals/market_data.md says why; this package only reads and writes the file and checks names.
It depends on nothing in Lightning but `lightning.core`.
"""
