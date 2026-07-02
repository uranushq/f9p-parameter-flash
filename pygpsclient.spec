# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for PyGPSClient.

Build with:
    pyinstaller pygpsclient.spec

Produces a one-folder distribution under dist/PyGPSClient/ with
PyGPSClient.exe as the launcher.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# bundle the packaged image / icon resources
datas = [("src/pygpsclient/resources", "pygpsclient/resources")]

# the underlying GNSS libraries use dynamic imports for their protocol
# databases, so pull in all their submodules and data explicitly
hiddenimports = []
for pkg in (
    "pygnssutils",
    "pyubxutils",
    "pyubx2",
    "pynmeagps",
    "pyrtcm",
    "pyspartn",
    "pysbf2",
    "pyqgc",
    "pyunigps",
    "paho.mqtt",
    "serial",
    "PIL",
):
    hiddenimports += collect_submodules(pkg)
    datas += collect_data_files(pkg)

a = Analysis(
    ["src/pygpsclient/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PyGPSClient",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon="src/pygpsclient/resources/pygpsclient.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PyGPSClient",
)
