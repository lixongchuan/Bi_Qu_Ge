# novel_gui_tool.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['novel_gui_tool.py'],
    pathex=[],
    binaries=[],  # 如果你需要嵌入 dll 等二进制文件可以放这里
    datas=[
        ('favicon.ico', '.')  # 添加图标到根目录
    ],
    hiddenimports=[],  # 如果你用了动态导入模块，放这里
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='novel_gui_tool',
    debug=False,
    bootloader_ignore_signals=False,
    clean=True,
    icon='favicon.ico',  # 图标路径
    win_limited_user=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='novel_gui_tool'
)