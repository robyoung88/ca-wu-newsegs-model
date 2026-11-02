"""Saving and loading of results as files in the results store.

Each type of result is saved in a format suited to it (parquet for dataframes, JSON for dictionaries, text and pickle otherwise) by a function registered with
`save_result`, and loaded by the loader registered for the extension of its file.
"""
from functools import singledispatch
import json
import os
from pathlib import Path
import pickle
from typing import Any, Callable, Union

import pandas as pd

#from newsegsmodelapp.postprocessing import cache

# -------------------------------------------------------------------------
# SAVE
# -------------------------------------------------------------------------

@singledispatch
def save_result(obj: Any, root_filename: str) -> str:
    """
    Fallback saver using pickle for unregistered types.
    
    Args:
        obj: The result object to persist.
        root_filename: Path/filename prefix (without extension).
        
    Returns:
        str: The full path of the saved file including extension.
    """
    filepath = f"{root_filename}.pickle"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        pickle.dump(obj, f)
    return filepath

@save_result.register(pd.DataFrame)
def _(df: pd.DataFrame, root_filename: str) -> str:
    filepath = f"{root_filename}.parquet"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    df.to_parquet(filepath, index=True)
    return filepath

@save_result.register(pd.Series)
def _(series: pd.Series, root_filename: str) -> str:
    filepath = f"{root_filename}_series.parquet"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    series.to_frame().to_parquet(filepath)
    return filepath

@save_result.register(dict)
@save_result.register(list)
def _(data: Union[dict, list], root_filename: str) -> str:
    import json
    filepath = f"{root_filename}.json"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return filepath

@save_result.register(str)
def _(text: str, root_filename: str) -> str:
    filepath = f"{root_filename}.txt"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    return filepath

# 3. Helper to register custom handlers dynamically at runtime
# REVIEW (unreferenced): no references to `register_saver` found in src/, scripts/ or data/.
def register_saver(type_: type) -> Callable[[Callable[[Any, str], str]], Callable[[Any, str], str]]:
    """Decorator to register custom result savers dynamically."""
    def decorator(func: Callable[[Any, str], str]):
        save_result.register(type_, func)
        return func
    return decorator


# -------------------------------------------------------------------------
# LOAD
# -------------------------------------------------------------------------

# Custom exception for unhandled file extensions
class UnsupportedFileExtensionError(ValueError):
    """Raised when no loader function is registered for the given file extension."""
    pass

LOADER_REGISTRY: dict[str, Callable[[Path], Any]] = {}

# Fallback / Default loader function
def default_loader(filepath: Path) -> Any:
    """Fallback loader for unregistered or pickle extensions."""
    if filepath.suffix.lower() in (".pkl", ".pickle"):
        with open(filepath, "rb") as f:
            return pickle.load(f)
            
    raise UnsupportedFileExtensionError(f"No loader registered for extension '{filepath.suffix}' on file '{filepath.name}'")

def register_loader(*extensions: str):
    """
    Decorator to register a function to one or more file extension strings.
    
    Example:
        @register_loader('.parquet', '.pq')
        def load_parquet(path: Path):
            return pd.read_parquet(path)
    """
    def decorator(func: Callable[[Path], Any]):
        for ext in extensions:
            # Ensure extensions start with '.' and are stored in lowercase
            formatted_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            LOADER_REGISTRY[formatted_ext] = func
        return func
    return decorator

#@cache.memoize()
def load_result(filepath: Union[str, Path]) -> Any:
    """
    Dispatches loading based on the file extension string value.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path.resolve()}")

    ext = path.suffix.lower()
    
    # Value lookup in registry dict, falling back to default_loader
    loader = LOADER_REGISTRY.get(ext, default_loader)
    return loader(path)

@register_loader('.parquet', '.pq')
def _load_parquet(filepath: Path) -> pd.DataFrame:
    return pd.read_parquet(filepath)

@register_loader(".json")
def _load_json(filepath: Path) -> Union[dict, list]:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

@register_loader(".txt")
def _load_txt(filepath: Path) -> str:
    return filepath.read_text(encoding="utf-8")

@register_loader(".pkl", ".pickle")
def _load_pickle(filepath: Path) -> Any:
    with open(filepath, "rb") as f:
        return pickle.load(f)
