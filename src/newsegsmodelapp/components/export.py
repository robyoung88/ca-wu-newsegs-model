"""Export of results of the deterministic run, DSA and PSA, for download.
"""
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

def _get_metamodel_deterministic_raw_data(metamodel: NewsegsMetaModel) -> pd.DataFrame | None:
    
    try:
        gen_res = metamodel.model.get_generation_result()
        grid_res = metamodel.model.get_grid_result()
        cs_res = metamodel.model.get_consumption_storage_result()
    except AttributeError:
        return None
    
    all_frames = [
        gen_res.meters_to_pandas(),
        gen_res.dsm_to_pandas(),
        grid_res.meters_to_pandas(),
        grid_res.dsm_to_pandas(),
        cs_res.meters_to_pandas(),
        cs_res.dsm_to_pandas()
    ]

    all_frames = [x for x in all_frames if not x.empty]
    if not len(all_frames):
        return None
    elif len(all_frames) == 1:
        return all_frames[0]
    else:
        odf = all_frames[0]
        for j in range(1, len(all_frames)):
            odf = odf.join(all_frames[j])

    return odf

def export_results(
    result_type: Literal['dsa','psa','det'],
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    project_id: str,
    metamodel_id: Optional[str] = None,
    contents_option: str = 'result',
    format_option: str = 'csv',
    result_level: Optional[str] = None,
):
    """Export the results of a deterministic run, or a DSA or PSA, of a project.

    Raises `NotImplementedError` for combinations that are not yet supported, such as DSA at project level.

    Args:
        result_type: The type of analysis: `det`, `dsa` or `psa`.
        project_provider: Provider of projects, metamodels and variables.
        result_provider: Provider of results.
        project_id: Id of the project.
        metamodel_id: Id of the metamodel.
        contents_option: What to export.
        format_option: The format of the file.
        result_level: The level of the results (project or metamodel).

    Returns:
        The data to download.
    """
    proj = project_provider.get_project(project_id)
    match result_type:
        case 'dsa':
            result_level = 'project' if result_level is None else result_level
            match result_level:
                case 'project':
                    raise NotImplementedError(f'DSA at project level not yet supported')
                case 'metamodel':
                    if metamodel_id is None:
                        metamodel_id = project_provider.get_focussed_metamodel_id(project_id)
                    mm = proj.get_metamodel_by_id(metamodel_id)
                    result_data, result_revision = result_provider.get_result(
                        'dsa_single_metamodel', mm.table_config, True
                    )
                    if result_data is None:
                        return None
                    stale = result_revision != mm.table_config.revision
                    assert isinstance(result_data, pd.DataFrame)
                case _:
                    raise ValueError(f'result_level not recognised: {result_level}')
        case 'psa':
            result_level = 'project' if result_level is None else result_level
            match result_level:
                case 'project':
                    raise NotImplementedError(f'PSA at project level not yet supported')
                case 'metamodel':
                    if metamodel_id is None:
                        metamodel_id = project_provider.get_focussed_metamodel_id(project_id)
                    mm = proj.get_metamodel_by_id(metamodel_id)
                    result_data, result_revision = result_provider.get_result(
                        'psa_single_metamodel', mm.table_config, True
                    )
                    if result_data is None:
                        return None
                    stale = result_revision != mm.table_config.revision
                    assert isinstance(result_data, pd.DataFrame)
                case _:
                    raise ValueError(f'result_level not recognised: {result_level}')
        case 'det':
            result_level = 'metamodel' if result_level is None else result_level
            match result_level:
                case 'project':
                    raise NotImplementedError('Deterministic results export for full project not yet supported')
                case 'metamodel':
                    if metamodel_id is None:
                        metamodel_id = project_provider.get_focussed_metamodel_id(project_id)
                    mm = proj.get_metamodel_by_id(metamodel_id)
                    stale = mm.model.reattach_results(result_provider)

                    result_data = _get_metamodel_deterministic_raw_data(mm)
                    if result_data is None:
                        return None
                    assert isinstance(result_data, pd.DataFrame)
                case _:
                    raise ValueError(f'result_level not recognised: {result_level}')
        case _:
            raise ValueError(f'result_type not recognised: {result_type}')
    
    def _strip_index_tz(df):
        index = df.index
        if getattr(index, 'tz', None) is not None:
            df = df.copy()
            df.index = index.tz_localize(None)
        return df

    def _make_project_filename_stub():
        proj_metadata = project_provider.get_component_metadata(project_id, 'label')
        proj_name = proj_metadata.get('label')
        return f'{proj_name}-{result_type}-results'

    def _make_metamodel_filename_stub(metamodel_id):
        mm_metadata = project_provider.metamodel_provider.get_component_metadata(metamodel_id, 'label')
        mm_name = mm_metadata.get('label')
        return f'{mm_name}-{result_type}-results'

    match result_level:
        case 'project':
            file_name_stub = _make_project_filename_stub()
        case 'metamodel':
            file_name_stub = _make_metamodel_filename_stub(metamodel_id)

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

            match result_level:
                case 'project':
                    config_dict = proj.to_dict_repr()
                    config_file_name = f'{proj.name}-config.json'
                case 'metamodel':
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
                    