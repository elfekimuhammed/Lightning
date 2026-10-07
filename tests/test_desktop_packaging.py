from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_windows_checkout_has_no_reserved_device_file():
    # On Windows, NUL exists as a virtual device even without a directory entry.
    assert "nul" not in {entry.name.casefold() for entry in ROOT.iterdir()}


def test_app_entry_import_does_not_load_windows_gui_or_open_data():
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-c", "import desktop_app, sys; assert 'webview' not in sys.modules; assert 'clr' not in sys.modules; assert sys.platform == 'win32' or 'winreg' not in sys.modules; assert 'lightning.bootstrap' not in sys.modules"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
