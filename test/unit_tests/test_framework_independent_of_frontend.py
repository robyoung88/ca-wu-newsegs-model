"""
The framework (`newsegsmodelframework`) does not depend on Dash or on plotting libraries (#156): every one of its
modules imports with them blocked. Figures are drawn by `newsegsmodelutils.plots`, and Dash components by the app.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

_SRC = Path(__file__).resolve().parents[2] / 'src'

_SCRIPT = r'''
import importlib.abc
import pkgutil
import sys

BLOCKED = {'dash', 'dash_bootstrap_components', 'dash_daq', 'dash_iconify', 'dash_leaflet', 'dash_ag_grid',
           'plotly', 'matplotlib', 'seaborn'}

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target = None):
        if name.split('.')[0] in BLOCKED:
            raise ImportError(f'{name} is blocked: the framework must not depend on it')
        return None

sys.meta_path.insert(0, Blocker())

import newsegsmodelframework
import newsegsmodelframework.register_plugins  # noqa: F401
failed = []
for module in pkgutil.walk_packages(newsegsmodelframework.__path__, prefix = 'newsegsmodelframework.'):
    try:
        importlib.import_module(module.name)
    except ImportError as e:
        failed.append(f'{module.name}: {e}')
print('\n'.join(failed))
sys.exit(1 if failed else 0)
'''

class TestFrameworkIndependentOfFrontend(unittest.TestCase):

    def test_imports_without_dash_or_plotting(self):
        env = {**os.environ, 'PYTHONPATH': str(_SRC)}
        result = subprocess.run(
            [sys.executable, '-c', 'import importlib\n' + _SCRIPT],
            cwd = _SRC.parent, env = env, capture_output = True, text = True, timeout = 600,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr[-3000:])
