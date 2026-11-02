"""Reusable components of the Dash app: layouts, callbacks and the components of inputs, results, maps and navigation.

Only `CONFIGURATION_UPDATE_TRIGGER_ID` is exposed here. The modules directly under this package are imported by
`newsegsmodelapp.register_plugins`, so that the input handlers and other functions they register are available.

Modules:
    constants: Constants shared by the components.
    navigation: The navigation bar, including the link to this documentation.
    icons: The icon library.
    project_selector: Choosing and managing projects and snapshots.
    configuration_selector: Choosing and managing the configurations (metamodels) of a project.
    map: The site selector.
    input_components: The inputs of variable parameters, and the handler of their changes.
    composite_input_components: Inputs which combine input components and variable components.
    variable_identification: Identification of the components of variables.
    energy_balance_estimation: Rough estimates of the energy balance for feedback.
    stats: Presentation of statistics of results.
    export: Export of results.
    result_file: Saving and loading results as files.
    get_focussed_metamodel: Getting the focussed metamodel of a project.
    callback_utils: Helpers for callbacks.
    serialisable_dataclass: A dataclass that converts to and from dictionaries.
    typed_dash_bootstrap_components: Dash bootstrap components typed for static analysis.

Subpackages:
    callbacks: Callbacks for inputs, actions, results and timeseries.
    layouts: Layouts of pages and cards.
    variable_dash_component: Inputs for the variables of a metamodel on each page.
    requesthandler: Interface of the creator and monitor of requests.
    feedback: Feedback graphs.
"""
from .constants import CONFIGURATION_UPDATE_TRIGGER_ID

__all__ = [
    'CONFIGURATION_UPDATE_TRIGGER_ID',
]
