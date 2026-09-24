"""Import this module to traverse plugin directories and ensure that registries are prepared"""
import importlib
import pkgutil

def load_plugins_recursive(package):
    """
    Recursively loads all submodules under a root package.
    Returns a dictionary mapping full module names to imported module objects.
    """
    discovered_plugins = {}
    
    # walk_packages scans the package path recursively
    for module_info in pkgutil.walk_packages(
        package.__path__, 
        prefix=f"{package.__name__}."
    ):
        # Dynamically import each discovered submodule
        module = importlib.import_module(module_info.name)
        discovered_plugins[module_info.name] = module
        
    return discovered_plugins

# Pages must be loaded before contents
import newsegsmodelapp.plugins.pages as pages
def load_pages_plugins():
    return load_plugins_recursive(pages)

import newsegsmodelapp.plugins.models as models
def load_models_plugins():
    return load_plugins_recursive(models)

load_pages_plugins()
load_models_plugins()


import newsegsmodelapp.components as components
def load_components():
    d = {}
    for info in pkgutil.iter_modules(
        components.__path__, prefix = 'newsegsmodelapp.components.'
    ):
        d[info.name] = importlib.import_module(info.name)
    return d
load_components()
