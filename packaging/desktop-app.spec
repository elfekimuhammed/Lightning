"""Build with: pyinstaller --clean --noconfirm packaging/desktop-app.spec"""
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))

# Templates, local styles/fonts, migrations and other package resources must travel
# with the frozen app. Profile databases stay in Documents/Lightning at runtime.
datas = collect_data_files("lightning") + collect_data_files("tzdata")
if sys.platform == "win32":
    datas += copy_metadata("pywebview")

analysis = Analysis(
    [str(root / "desktop_app.py")],
    pathex=[str(root)],
    datas=datas,
    hiddenimports=[
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on",
    ],
    excludes=[
        "tkinter",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "qtpy",
        "gi",
        "cefpython3",
        "pytest",
        "importlinter",
    ],
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Lightning",
    icon=str(root / "lightning" / "ui" / "static" / "lightning.ico"),
    console=False,
    upx=False,
    disable_windowed_traceback=True,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="Lightning", upx=False)
