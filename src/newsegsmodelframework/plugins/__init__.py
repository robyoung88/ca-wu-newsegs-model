"""Plugins of the framework: the registry of model types and the project plugins that populate it.

Importing this package, which Python does before importing any module within it, imports
every project plugin. `PROJECT_FACTORIES` is therefore populated wherever it is imported
from, without needing `newsegsmodelframework.register_plugins` to have been imported first.

Modules:
    registers: `PROJECT_FACTORIES` and `register_project_factory`.
    projects: The project plugins, one module for each model type.
"""
import importlib
import pkgutil
from types import ModuleType


def _load_project_plugins() -> dict[str, ModuleType]:
    """Import every module in `newsegsmodelframework.plugins.projects`, so that they register their factories.

    Modules are imported in name order, so the first of them provides the `'default'` factory.

    Returns:
        Dictionary of the modules by name.
    """
    from . import projects
    return {
        info.name: importlib.import_module(info.name)
        for info in sorted(
            pkgutil.iter_modules(projects.__path__, prefix = projects.__name__ + '.'),
            key = lambda info: info.name
        )
    }


PROJECT_PLUGINS = _load_project_plugins()
"""The project plugin modules, by name."""
