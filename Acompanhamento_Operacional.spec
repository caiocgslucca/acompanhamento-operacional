# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas=[('app/static','app/static')]
binaries=[]
hiddenimports=[]
for package in ['fastapi','uvicorn','starlette','pydantic','polars','pyarrow','duckdb','openpyxl','apscheduler','jinja2','reportlab']:
    package_datas,package_binaries,package_hidden=collect_all(package)
    datas+=package_datas; binaries+=package_binaries; hiddenimports+=package_hidden
hiddenimports+=collect_submodules('uvicorn')

a=Analysis(['desktop_launcher.py'],pathex=['.'],binaries=binaries,datas=datas,hiddenimports=sorted(set(hiddenimports)),hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['pytest','httpx'],noarchive=False,optimize=1)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Acompanhamento_Operacional',icon='app-icon.ico',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=True,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,upx_exclude=[],name='Acompanhamento_Operacional')
