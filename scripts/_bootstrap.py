import sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'tmp' / 'matplotlib'))
sys.path.insert(0, str(ROOT))
# Legacy project-local dependencies are opt-in. A virtual environment owns its site-packages.
# and must not be shadowed by an incomplete or stale .deps folder.
if os.environ.get('QF_USE_LEGACY_DEPS') == '1' and (ROOT / '.deps').exists():
    sys.path.insert(0, str(ROOT / '.deps'))
