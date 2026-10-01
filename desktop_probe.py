"""PyInstaller entry point for the Windows feasibility gate, not the beta app."""
from lightning.desktop.probe import run

if __name__ == "__main__":
    raise SystemExit(run())
