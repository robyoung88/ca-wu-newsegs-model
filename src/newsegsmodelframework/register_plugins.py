"""Import this module to traverse plugin directories and ensure that registries are prepared"""
import importlib
import pkgutil

def load_project_factories():
    """Load project factories.

    TODO: Add a description.

    Returns:
        TODO.
    """
    import newsegsmodelframework.plugins.projects
    pf_dict = {}
    for info in pkgutil.iter_modules(
        newsegsmodelframework.plugins.projects.__path__, prefix = 'newsegsmodelframework.plugins.projects.'
    ):
        pf_dict[info.name] = importlib.import_module(info.name)
    return pf_dict

load_project_factories()
