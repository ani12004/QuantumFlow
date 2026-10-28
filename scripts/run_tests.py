import _bootstrap
import os
import tempfile
import uuid
from pathlib import Path

import pytest

# A caller may override the scratch location when the default Windows temp
# directory or a previous project test folder belongs to a different identity.
run_root = Path(os.environ.get('QF_TEST_TEMP', tempfile.gettempdir())) / 'quantumflow-blr-tests' / uuid.uuid4().hex
run_root.mkdir(parents=True, exist_ok=False)
os.environ['TEMP'] = str(run_root)
os.environ['TMP'] = str(run_root)
tempfile.tempdir = str(run_root)

if __name__ == '__main__':
    raise SystemExit(pytest.main([
        str(_bootstrap.ROOT / 'tests'),
        '-q',
        '-p', 'no:cacheprovider',
        '--basetemp=' + str(run_root / 'pytest'),
        '--junitxml=' + str(_bootstrap.ROOT / 'reports' / 'tests.xml'),
    ]))
