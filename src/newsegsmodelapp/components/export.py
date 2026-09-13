import io
import json
import tempfile
from typing import Any, Literal, Optional
import zipfile

from dash import dcc
import pandas as pd
import pathvalidate

from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.util import jsonfuncs

def metamodel_to_config_file(mm: NewsegsMetaModel) -> dict[str, Any]:
    """
    Encapsulate a model and finance configuration in a dictionary.
    """
    
    odict = {
        'config_name': mm.name,
        'metamodel': mm.to_dict_repr(),
    }
    return odict

def export_results(
    result_type: Literal['dsa','psa','det'],
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    active_project_id: str,
    selected_metamodel_index: Optional[int] = None,
    contents_option: str = 'result',
    format_option: str = 'csv',
):
    result_level = 'project'
    match result_type:
        case 'dsa':
            result_data = pd.DataFrame([])#postprocess_utils.get_dsa_raw_data(selected_configuration, acm)
        case 'psa':
            result_data = pd.DataFrame([])#postprocess_utils.get_psa_raw_data(selected_configuration, acm)
        case 'det':
            result_level = 'metamodel'
            result_data = pd.DataFrame([])#postprocess_utils.get_det_raw_data(selected_configuration, acm)
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

    def _make_project_filename_stub():
        proj_metadata = project_provider.get_component_metadata(active_project_id, 'label')
        proj_name = proj_metadata.get('label')
        return f'{proj_name}-{result_type}-results'

    def _make_metamodel_filename_stub(metamodel_index):
        mm_ids = project_provider.list_project_metamodel_ids(active_project_id)
        mm_id = mm_ids[metamodel_index]
        mm_metadata = project_provider.metamodel_provider.get_component_metadata(mm_id, 'label')
        mm_name = mm_metadata.get('label')
        return f'{mm_name}-{result_type}-results'

    match result_level:
        case 'project':
            file_name_stub = _make_project_filename_stub()
        case 'metamodel':
            if not selected_metamodel_index:
                file_name_stub = _make_project_filename_stub()
            else:
                file_name_stub = _make_metamodel_filename_stub(selected_metamodel_index)

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

            proj = project_provider.get_project(active_project_id)
            match result_level:
                case 'project':
                    config_dict = proj.to_dict_repr()
                    config_file_name = f'{proj.name}-config.json'
                case 'metamodel':
                    if selected_metamodel_index is None:
                        config_dict = proj.to_dict_repr()
                        config_file_name = f'{proj.name}-config.json'
                    else:
                        mm = proj.metamodels[selected_metamodel_index]
                        config_dict = mm.to_dict_repr()
                        config_file_name = f'{mm.name}-config.json'
                case _:
                    raise ValueError(f'result_level not recognised: {result_level}')
            
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
                        config_dict,
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
                                    config_file_name
                                ),
                                configfile.read()
                            )
                        zip_buffer.seek(0)
                        return dcc.send_bytes(
                            lambda buffer: buffer.write(zip_buffer.getvalue()),
                            filename = out_fn
                        )
                    