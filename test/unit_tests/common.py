"""
Functionality and imports common to all unit tests
"""
from pathlib import Path

def get_data_dir(path: Path, root: str = 'ca-wu-newsegs-model'):
    parts = path.parts
    if root not in parts:
        raise ValueError(f"Directory '{root}' not found in path {path}")

    idx = parts. index(root)
    return Path(*parts[: idx + 1]) / 'data'
