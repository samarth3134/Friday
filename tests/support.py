"""Load source without starting the application or requiring optional packages."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, stubs=None):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    replacements = {'requests': MagicMock(name='requests')}
    replacements.update(stubs or {})
    with patch.dict(sys.modules, replacements):
        spec.loader.exec_module(module)
    return module
