# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for ReferenceMiner

Build with: pyinstaller referenceminer.spec
Output: dist/ReferenceMiner.exe
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
from pathlib import Path

block_cipher = None

# Hidden imports for packages that PyInstaller doesn't detect automatically
hiddenimports = [
    # FastAPI/Starlette/Uvicorn
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    'starlette.routing',
    'starlette.responses',
    'starlette.middleware',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'anyio._backends._asyncio',

    # Document processing
    'fitz',  # PyMuPDF
    'pymupdf',
    'docx',
    'PIL',
    'PIL.Image',

    # Data processing
    'pandas',
    'numpy',
    'openpyxl',

    # BM25 and text processing
    'rank_bm25',
    'jieba',
    'jieba.analyse',
    'jieba.posseg',

    # HTTP client
    'httpx',
    'httpx._transports',
    'httpx._transports.default',
    'httpcore',

    # Pydantic
    'pydantic',
    'pydantic.deprecated',
    'pydantic.deprecated.decorator',

    # Standard library
    'multiprocessing',
    'json',
    'email.mime.multipart',
    'email.mime.text',
]

# Collect data files
datas = [
    # Frontend dist folder (built Vue app)
    ('frontend/dist', 'frontend'),

    # jieba dictionary files (required for Chinese text processing)
    *collect_data_files('jieba'),

    # LLM prompt templates
    ('src/refminer/llm/prompts', 'refminer/llm/prompts'),
]

# Analysis
a = Analysis(
    ['launcher.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy ML libraries (BM25-only mode)
        'sentence_transformers',
        'torch',
        'torchvision',
        'torchaudio',
        'transformers',
        'faiss',
        'faiss_cpu',
        'tensorflow',
        'keras',
        'sklearn',
        'scipy',
        # Exclude unused packages
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ReferenceMiner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show console window for logs; set to False for GUI-only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment if you have an icon file
)
