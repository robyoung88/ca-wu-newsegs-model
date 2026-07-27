import copy
import inspect
import io
import json
import logging
import tempfile
import time

from collections.abc import Sequence
from dataclasses import KW_ONLY, dataclass, field
from dataclasses import asdict as dc_asdict
from typing import Any, Callable, Literal, cast
from typing import TypeVar
from typing import overload
from typing import Optional
from typing import List
import datetime
import uuid
import zipfile

from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
import pathvalidate
from useful_types import SequenceNotStr

from newsegsbrowser.callbacks.configuration_selector_callbacks import metamodel_to_dict
from newsegsbrowser.postprocess import postprocess_utils
from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance

from newsegsbrowser.icons import get_icon
from newsegssensitivity import optim
from util import jsonfuncs

logger = logging.getLogger(__name__)

def create_numeric_card_input(
    icon_name: str | SequenceNotStr[str],
    label: str,
    input_id: str
):
    return html.Div([
        html.H5([
            get_icon(icon_name, None, 'default'),
            html.Span(label+":", className='mr-3')
        ],
        style={'display':'inline'}),
        dbc.Input(id=input_id,
                  type='number',
                  placeholder=0.0,
                  debounce=True,
                  style={
                    'display':'inline-block',
                    'float':'right',
                    'width':'30%'
                  })
    ])

def create_numeric_input_compound_key(
    type_id: str,
    key: str,
    section: str | None = None,
    subindex: int = 0,
    parameter_index: int = 0,
    vector_location: int = 0,
    placeholder: int | float | str = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):
    if section is None:
        section = 'None'
    
    input_id = {
        'type': type_id,
        'key': key,
        'section': section,
        'subindex': subindex,
        'parameter_index': parameter_index,
        'vector_location': vector_location,
    }
    if float(int(step)) == float(step):
        step = int(step)
        cn = f'dynamic-step-field step-val-{step:d}'
    else:
        cn = f'dynamic-step-field step-val-{step:f}'
    
    return dbc.Input(
        id = input_id,
        type = 'number',
        value = value,
        placeholder = placeholder,
        debounce = True,
        min = min,
        max = max,
        step = 'any',
        # style = {
        #     'display':'inline-block',
        #     'float':'right',
        #     'width':'30%'
        # },
        className = cn,
    )

def create_numeric_card_input_compound_key(
    icon_name: str | SequenceNotStr[str],
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
    subindex: int = 0,
    parameter_index: int = 0,
    vector_location: int = 0,
    placeholder: int | float = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):  
    return html.Div([
        html.H5(
            [
                get_icon(icon_name, None, 'default'),
                html.Span(label+":", className='mr-3')
            ],
            style={'display':'inline'}
        ),
        create_numeric_input_compound_key(
            type_id,
            key,
            section,
            subindex,
            parameter_index,
            vector_location,
            placeholder,
            value,
            min,
            max,
            step
        )
    ])

def unescape_html_icons(html_text):
    return (
        html_text
        .replace('<th>&lt;','<th><')
        .replace('"&gt;&lt;','"><')
        .replace('i&gt;', 'i>')
    )

##### Functions for app control - Actions, Queue items etc #####

def compose_configuration(
    name: str,
    mdl: newsegsmodel.NewsegsModel | str,
    fnc: newsegsfinance.NewsegsFinance | str,
    model_class: str = 'SprakeModel',
    finance_class: str = 'SprakeFinance',
) -> dict:
    """
    A 'Composed Configuration' - a named combination of a model and a finance.

    Args:
        name: A compulsory name for the configuration.
        mdl: A NewsegsModel or a model id.
        fnc: A NewsegsFinance or a finance id.
        model_class (Optional): A string giving the class of the model.
        finance_class (Optional): A string giving the class of the finance.
    """
    if isinstance(mdl, newsegsmodel.NewsegsModel):
        mdl_id = mdl.id
    else:
        mdl_id = mdl
    
    if isinstance(fnc, newsegsfinance.NewsegsFinance):
        fnc_id = fnc.id
    else:
        fnc_id = fnc
    
    rval = {
        'uuid': str(uuid.uuid4()),
        'name': name,
        'model_id': mdl_id,
        'finance_id': fnc_id,
        'model_class': model_class,
        'finance_class': finance_class,
    }
    rval['id'] = 'c-' + rval['uuid']
    
    return rval

@dataclass
class Action:
    """
    Class for dispatching actions
    """
    
    _: KW_ONLY
    type: str
    time: float = field(default_factory = time.time)
    debounce: bool = True

    @classmethod
    def from_dict(cls, env):      
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        return dc_asdict(self)

@dataclass
class MetaModelAction(Action):
    metamodel_id: str
    _: KW_ONLY
    type: str = field(init = False)

@dataclass
class MetaModelVariableSyncAction(MetaModelAction):
    _: KW_ONLY
    type: str = 'metamodel_variable_sync_action'
    
@dataclass
class VariableAction(MetaModelAction):
    metamodel_id: str
    section: str
    key: str
    subindex: int = 0
    _: KW_ONLY
    model_class: Literal['model', 'finance'] = 'model'

@dataclass
class ModelConfigInterfaceAction(VariableAction):
    parameter_index: int = 0
    vector_location: int = 0

    def __post_init__(self):
        match self.model_class:
            case 'model':
                self.type = 'model_config_interface_update'
            case 'finance':
                self.type = 'finance_config_interface_update'

@dataclass
class DSAImpactingInterfaceAction(VariableAction):
    
    action_key: str = 'dsa_input_change'
    bounds_type_change: bool = False
    selected_status_change: bool = False
    _: KW_ONLY
    type: str = 'dsa_impacting_interface_action'

@dataclass
class PSAImpactingInterfaceAction(VariableAction):
    
    action_key: str = 'psa_input_change'
    selected_status_change: bool = False
    _: KW_ONLY
    type: str = 'psa_impacting_interface_action'

@dataclass
class MetaModelProcessAction(Action):
    metamodel_id: str = ''
    type: Literal[ # pyright: ignore[reportIncompatibleVariableOverride]
        'result_update_request',
        'dsa_run_request',
        'psa_run_request',
        'optim_run_request',
    ]
    action_key: str = field(init = False)
    _: KW_ONLY
    force: bool = False

    def __post_init__(self):
        match self.type:
            case 'result_update_request':
                self.action_key = 'result_update'
            case 'dsa_run_request':
                self.action_key = 'dsa_run'
            case 'psa_run_request':
                self.action_key = 'psa_run'
            case 'optim_run_request':
                self.action_key = 'optim_run'
            case _:
                self.action_key = ''

@dataclass
class ModelRunAction(MetaModelProcessAction):
    metamodel_id: str = ''
    model_id: str = ''
    type: str = 'model_run_request' # pyright: ignore[reportIncompatibleVariableOverride]
    action_key: str = 'model_run'

    def __post_init__(self):
        """
        Override the setting of MetaModelProcessAction action key
        """
        return

@dataclass
class FinanceRunAction(ModelRunAction):
    type: str = 'finance_run_request'
    action_key: str = 'finance_run'
    finance_id: str = ''

@dataclass
class ResultUpdateAction(MetaModelProcessAction):
    type: str = 'result_update_request' # pyright: ignore[reportIncompatibleVariableOverride]

@dataclass
class DSARunAction(MetaModelProcessAction):
    type: str = 'dsa_run_request' # pyright: ignore[reportIncompatibleVariableOverride]

@dataclass
class PSARunAction(MetaModelProcessAction):
    type: str = 'psa_run_request' # pyright: ignore[reportIncompatibleVariableOverride]
    samples: int = 1000
    return_draws: bool = False
    seed: float | None = None

@dataclass
class OptimRunAction(MetaModelProcessAction):
    type: str = 'optim_run_request' # pyright: ignore[reportIncompatibleVariableOverride]
    variables: list[optim.OptimVariable] = field(default_factory = list)
    target: str = 'net_present_value_discounted'
    method: str = 'Nelder-Mead'
    metamodel_dup: str = ''

def metamodel_variable_sync_action(**kwargs):
    return MetaModelVariableSyncAction.from_dict(kwargs)

def model_interface_action(
    **kwargs
):
    return ModelConfigInterfaceAction.from_dict(kwargs)

def finance_interface_action(
    **kwargs
):
    kwargs.update({
        'model_class': 'finance'
    })
    return ModelConfigInterfaceAction.from_dict(kwargs)

def dsa_impacting_interface_action(
    **kwargs
):
    """
    Action to raise if an interface change has impacted a DSA value.

    Primary outcome is the update of DSA headers.
    """
    return DSAImpactingInterfaceAction.from_dict(kwargs)

def psa_impacting_interface_action(
    **kwargs
):
    """
    Action to raise if an interface change has impacted a PSA value.

    Primary outcome is the update of PSA headers.
    """
    return PSAImpactingInterfaceAction.from_dict(kwargs)

def model_run_interface_action(
    **kwargs
):
    return ModelRunAction.from_dict(kwargs)

def result_update_interface_action(
    **kwargs
):
    return ResultUpdateAction.from_dict(kwargs)

def model_run_request(
    **kwargs
):
    return ModelRunAction.from_dict(kwargs)

def finance_run_request(
   **kwargs
):
    return FinanceRunAction.from_dict(kwargs)


def metamodel_process_request(
    **kwargs
):
    return MetaModelProcessAction.from_dict(kwargs)

def dsa_run_request(
    **kwargs
):
    return DSARunAction.from_dict(kwargs)

def psa_run_request(
    **kwargs
):
    return PSARunAction.from_dict(kwargs)

def optim_run_request(
    **kwargs
):
    return OptimRunAction.from_dict(kwargs)

##### Callback helpers #####
def get_options(
    option_ids: list[dict[str, str]],
    option_values: list[Any],
    page: str,
    keys: list[str]
) -> dict[str, Any]:
    odict = {}
    for id, val in zip(option_ids, option_values):
        if id.get('page') and id.get('key') in keys:
            odict[id['key']] = val
    return odict

def get_variable_keyed_data(
    section: str,
    key: str,
    subindex: int,
    ids,
    values
):
    for id, val in zip(ids, values):
        if (
            id.get('section') == section
            and id.get('key') == key
            and id.get('subindex') == subindex
        ):
            return val

def export_results(
    result_type: Literal['dsa','psa','det'],
    selected_configuration: dict[str, Any],
    app: Dash,
    contents_option: str = 'result',
    format_option: str = 'csv',
):
    match result_type:
        case 'dsa':
            result_data = postprocess_utils.get_dsa_raw_data(selected_configuration, app)
        case 'psa':
            result_data = postprocess_utils.get_psa_raw_data(selected_configuration, app)
        case 'det':
            result_data = postprocess_utils.get_det_raw_data(selected_configuration, app)
        case _:
            raise ValueError(f'result_type not recognised: {result_type}')
    if result_data is None:
        return None
    
    def _strip_index_tz(df):
        index = df.index
        if getattr(index, 'tz', None) is not None:
            df = df.copy()
            df.index = index.tz_localize(None)
        return df
    
    mm = app.metamodels.get(selected_configuration['metamodel_id'])
    file_name_stub =f'{mm.name}-{result_type}-results'
    match contents_option:
        case 'result':
            out_fn = pathvalidate.sanitize_filename(f'{file_name_stub}.{format_option}')
        case 'result_and_config':
            out_fn = pathvalidate.sanitize_filename(f'{file_name_stub}.zip')
        case _:
            raise ValueError(f'contents_option not recognised: {contents_option}')
    
    match contents_option:
        case 'result':
            match format_option:
                case 'csv':
                    return dcc.send_data_frame(result_data.to_csv, out_fn)
                case 'xlsx':
                    result_data_for_export = _strip_index_tz(result_data)
                    return dcc.send_data_frame(
                        result_data_for_export.to_excel,
                        out_fn,
                        sheet_name = f'{result_type} results'
                    )
                case _:
                    raise ValueError(f'format_option not recognised: {format_option}')
        case 'result_and_config':
            result_fn = pathvalidate.sanitize_filename(f'{file_name_stub}.{format_option}')
            match format_option:
                case 'csv':
                    results_mode = 'w+b'
                case 'xlsx':
                    results_mode = 'w+b'
                case _:
                    raise ValueError(f'format_option not recognised: {format_option}')
            
            with tempfile.TemporaryFile(mode = results_mode, suffix = result_fn) as resultsfile:
                match format_option:
                    case 'csv':
                        result_data.to_csv(resultsfile)
                    case 'xlsx':
                        result_data_for_export = _strip_index_tz(result_data)
                        result_data_for_export.to_excel(resultsfile, sheet_name = f'{result_type} results')
                resultsfile.seek(0)

                with tempfile.TemporaryFile(mode = 'w+', suffix = '.json') as configfile:
                    json.dump(
                        metamodel_to_dict(mm),
                        configfile,
                        cls = jsonfuncs.NumpyEncoder,
                        sort_keys = False, indent = 4
                    )
                    configfile.seek(0)

                    with io.BytesIO() as zip_buffer:
                        with zipfile.ZipFile(zip_buffer, mode = 'w', compression = zipfile.ZIP_DEFLATED) as ziparchive:
                            ziparchive.writestr(result_fn, resultsfile.read())
                            ziparchive.writestr(
                                pathvalidate.sanitize_filename(
                                    f'{mm.name}-config.json'
                                ),
                                configfile.read()
                            )
                        zip_buffer.seek(0)
                        return dcc.send_bytes(
                            lambda buffer: buffer.write(zip_buffer.getvalue()),
                            filename = out_fn
                        )
                    
def safe_remove_finance(
    finance_id: str,
    configurations: list[str],
    app: Dash,
):
    has_finance = [x for x in configurations if json.loads(x)['finance_id'] == finance_id]
    if len(has_finance) == 0:
        app.remove_finance(finance_id)

def safe_remove_model(
    model_id: str,
    configurations: list[str],
    app: Dash,
):
    has_model = [x for x in configurations if json.loads(x)['finance_id'] == model_id]
    if len(has_model) == 0:
        app.remove_model(model_id)

def safe_remove_metamodel(
    metamodel_id: str,
    configurations: list[str],
    app: Dash,
):
    """
    Remove a metamodel, its associated model and finance, and results, from app.

    configurations should already have the metamodel removed.
    """
    mm = app.metamodels.get(metamodel_id)
    if mm is None:
        return
    safe_remove_finance(mm.finance.id, configurations, app)
    safe_remove_model(mm.model.id, configurations, app)
    # Always safe to drop the metamodel, just don't necessarily remove the children
    app.remove_metamodel(mm.id, False)
    return

def set_progression_factory(
    set_progress: Callable[[str], None],
    default_message: str = ''
) -> Callable[[int,int], None]:
    t0 = time.time()
    def set_progression(value: int, max: int) -> None:
        tx = time.time()
        dt = tx - t0
        if value != 0:
            rate_ = dt / value
            expected_ = rate_ * max
            remaining_ = expected_ - dt
            if remaining_ > 3600:
                report_time = time.strftime('%H:%M:%S', time.gmtime(remaining_))
            elif remaining_ > 60:
                report_time = time.strftime('%M:%S', time.gmtime(remaining_))
            else:
                report_time = time.strftime('%S seconds', time.gmtime(remaining_))
            msg = f'{value} / {max} iterations; {report_time} remaining'
        else:
            msg = default_message

        set_progress(
            json.dumps(
                dict(
                    value = str(value),
                    max = str(max),
                    message = msg
                )
            )
        )
    return set_progression

MODEL_RESULT_ATTRIBUTES = [
    {
        'aname': '_generation_result',
        'modname': 'generation'
    },
    {
        'aname': '_grid_result',
        'modname': 'grid'
    },
    {
        'aname': '_cs_result',
        'modname': 'consumption_storage'
    }
]

FINANCE_RESULT_ATTRIBUTES = []

def copy_result_attributes(
    ref_mdl: newsegsmodel.NewsegsModel | newsegsfinance.NewsegsFinance,
    dup_mdl: newsegsmodel.NewsegsModel | newsegsfinance.NewsegsFinance
):
    if not isinstance(dup_mdl, type(ref_mdl)):
        raise TypeError(f'Duplicate model (type {type(dup_mdl)}) is not the same type as reference model (type {type(ref_mdl)})')
    if isinstance(ref_mdl, newsegsmodel.NewsegsModel):
        attr_list = MODEL_RESULT_ATTRIBUTES
    elif isinstance(dup_mdl, newsegsfinance.NewsegsFinance):
        attr_list = FINANCE_RESULT_ATTRIBUTES
    else:
        raise TypeError(f'Reference model is not a recognised Newsegs model type: {type(ref_mdl)}')
    for resattr in attr_list:
        if hasattr(ref_mdl, resattr['aname']):
            setattr(
                dup_mdl,
                resattr['aname'],
                copy.copy(
                    getattr(
                        ref_mdl,
                        resattr['aname']
                    )
                )
            )
            getattr(dup_mdl, resattr['modname'])._dirty = getattr(
                ref_mdl,
                resattr['modname']
            )._dirty
    dup_mdl._dirty = ref_mdl._dirty

def duplicate_metamodel(
   metamodel_id: str,
   configurations: list[str],
   app: Dash, 
   copy_results = True,
) -> NewsegsMetaModel:
    mm_ref = app.metamodels.get(metamodel_id)
    if mm_ref is None:
        raise ValueError(f'Reference metamodel not found: {metamodel_id}')
    
    mm_dup = cast(NewsegsMetaModel, app.duplicate_metamodel(metamodel_id))
    mm_dup.name += ' Copy'

    new_config = mm_dup.to_config()
    configurations.append(json.dumps(new_config))

    # Copy model results
    if copy_results:
        copy_result_attributes(
            mm_ref.model,
            mm_dup.model
        )
        copy_result_attributes(
            mm_ref.finance,
            mm_dup.finance
        )

    return mm_dup

def has_metamodel_config_fields(
    cfg: dict[str, Any]
) -> bool:
    return (
        cfg.get('metamodel') is not None
        and cfg.get('model') is not None
        and cfg.get('finance') is not None
    )

def metamodel_from_configuration_file(
    cfg: dict[str, Any],
    selected_configuration: dict[str, Any],
    configurations: list[str],
    app: Dash,
    overwrite_selected_config = False,
) -> NewsegsMetaModel | None:
    """
    Generate a metamodel and configure it per a dictionary.

    Note that this will not automatically update the configurations list or
    selected configuration, and requires at least one metamodel present
    in the configurations list to duplicate.
    """
    # Check that the config has the minimum required fields
    if not has_metamodel_config_fields(cfg):
        raise ValueError('Invalid metamodel configuration file')
    
    if not overwrite_selected_config:
        try:
            working_mm = duplicate_metamodel(
                selected_configuration['metamodel_id'],
                configurations,
                app,
                copy_results = False
            )
        except (TypeError, ValueError) as e:
            logger.error(str(e))
            return None
    else:
        working_mm = app.metamodels.get(selected_configuration['metamodel_id'])
    
    try:
        # Store ids prior to update so we can ensure they are reset
        mm_id = working_mm.id
        mdl_id = working_mm.model.id
        fnc_id = working_mm.finance.id

        # Ensure that we hold the correct models and finances
        mdl = working_mm.model
        fnc = working_mm.finance

        working_mm.update(cfg['metamodel'])
        mdl.update(cfg['model'])
        fnc.update(cfg['finance'])

        # Reset the ids and links - just in case
        working_mm.id = mm_id
        mdl.id = mdl_id
        fnc.id = fnc_id
        fnc.set_model(mdl)
        working_mm.model = mdl
        working_mm.finance = fnc
        logger.info('metamodel loaded: %s, %s', working_mm.name, working_mm.id)

    except Exception as e:
        if not overwrite_selected_config:
            safe_remove_metamodel(
                working_mm.id,
                configurations,
                app
            )
        raise e
    
    return working_mm