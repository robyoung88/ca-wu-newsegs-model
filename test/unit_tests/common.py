"""
Functionality and imports common to all unit tests
"""
from pathlib import Path

# The repository root: this file is <root>/test/unit_tests/common.py
_REPO_ROOT = Path(__file__).resolve().parents[2]

def get_data_dir(path: Path | None = None, root: str = 'ca-wu-newsegs-model') -> Path:
    """The data directory of the repository.

    It is found from the location of this file, so that it depends neither on the working directory nor on the name
    of the checkout (on GitHub runners the checkout is <name>/<name>, so searching the path for <name> finds the wrong
    directory). `path` and `root` are accepted for compatibility, and ignored.
    """
    return _REPO_ROOT / 'data'
