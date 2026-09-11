"""Import this module to traverse plugin directories and ensure that registries are prepared"""
import importlib
import pkgutil

import newsegsmodelapp.newsegsbrowser.layouts as layouts
def load_layouts():
    layout_dict = {}
    for info in pkgutil.iter_modules(
        layouts.__path__, prefix = 'newsegsmodelapp.newsegsbrowser.layouts.'
    ):
        layout_dict[info.name] = importlib.import_module(info.name)
    return layout_dict
load_layouts()

import newsegsmodelapp.processes as processes
def load_processes():
    process_dict = {}
    for info in pkgutil.iter_modules(
        processes.__path__, prefix = 'newsegsmodelapp.processes.'
    ):
        process_dict[info.name] = importlib.import_module(info.name)
    return process_dict

load_processes()

import newsegsmodelapp.postprocessing.postprocesses as postprocesses
def load_postprocesses():
    d = {}
    for info in pkgutil.iter_modules(
        postprocesses.__path__, prefix = 'newsegsmodelapp.postprocessing.postprocesses.'
    ):
        d[info.name] = importlib.import_module(info.name)
    return d

load_postprocesses()

import newsegsmodelapp.postprocessing.tables
def load_tables():
    d = {}
    for info in pkgutil.iter_modules(
        newsegsmodelapp.postprocessing.tables.__path__, prefix = 'newsegsmodelapp.postprocessing.tables.'
    ):
        d[info.name] = importlib.import_module(info.name)
    return d

load_tables()

# This should cover both INPUT_CONTAINER_CONTENT_CREATORS and INPUT_SECTION_HEADER_CONTENT_CREATORS
import newsegsmodelapp.newsegsbrowser.layouts.inputs as input_layouts
def load_input_container_content_creators():
    d = {}
    for info in pkgutil.iter_modules(
        input_layouts.__path__, prefix = 'newsegsmodelapp.newsegsbrowser.layouts.inputs.'
    ):
        d[info.name] = importlib.import_module(info.name)
    return d

load_input_container_content_creators()

# import postprocessing.loaders
# def load_loaders():
#     d = {}
#     for info in pkgutil.iter_modules(
#         postprocessing.loaders.__path__, prefix = 'postprocessing.loaders.'
#     ):
#         d[info.name] = importlib.import_module(info.name)
#     return d

# load_loaders()



# import postprocessing.figures
# def load_figures():
#     d = {}
#     for info in pkgutil.iter_modules(
#         postprocessing.figures.__path__, prefix = 'postprocessing.figures.'
#     ):
#         d[info.name] = importlib.import_module(info.name)
#     return d

# load_figures()
