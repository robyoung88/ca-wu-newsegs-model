"""Registers for model framework plugins"""

from typing import Callable

from newsegsmodelframework.newsegsproject import NewsegsProject


PROJECT_FACTORIES: dict[str, Callable[[], NewsegsProject]] = {}
"""Register of functions to generate a new project.

Index by model type.
"""

def register_project_factory(name: str):
    """Add a project generation function to PROJECT_FACTORIES
    
    The name should correspond to the model type.
    """
    def decorated(func):
        PROJECT_FACTORIES[name] = func
        if 'default' not in PROJECT_FACTORIES:
            PROJECT_FACTORIES['default'] = func
        return func
    return decorated
