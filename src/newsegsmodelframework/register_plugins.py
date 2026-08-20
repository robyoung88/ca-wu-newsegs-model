"""Import this module to traverse plugin directories and ensure that registries are prepared"""
import importlib
import pkgutil

import newsegsmodelframework.plugins.projects
def load_project_factories():
    pf_dict = {}
    for info in pkgutil.iter_modules(
        newsegsmodelframework.plugins.projects.__path__, prefix = 'newsegsmodelframework.plugins.projects.'
    ):
        pf_dict[info.name] = importlib.import_module(info.name)
    return pf_dict

load_project_factories()
