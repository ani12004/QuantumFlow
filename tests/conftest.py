import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Tests run against the active interpreter environment.  Legacy .deps remains
# available only through the explicit QF_USE_LEGACY_DEPS bootstrap opt-in.
sys.path.insert(0, str(ROOT))
