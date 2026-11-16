"""Export of the results of the deterministic run, DSA and PSA of configurations, for download.

The results of one configuration, or of several, are exported as csv or xlsx:

- One configuration: a single `<config>-<type>-results.csv` or `.xlsx`.
- Several configurations as csv: a zip of one `<config>-<type>-results.csv` per configuration.
- Several configurations as xlsx: one workbook, `<project>-<type>-results.xlsx`, with a sheet per configuration.

With the configurations included, the download is a zip of the results and a `<config>-config.json` per
configuration, which the DSA and PSA pages can upload again.
"""
from collections.abc import Sequence
from dataclasses import dataclass, field
import io
import json
import logging
import re
from typing import Any, Literal
import zipfile

from dash import dcc
import pandas as pd
import pathvalidate

from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.util import jsonfuncs

logger = logging.getLogger(__name__)

ResultType = Literal['det', 'dsa', 'psa']
FormatOption = Literal['csv', 'xlsx']

RESULT_TYPE_LABELS: dict[str, str] = {'det': 'deterministic', 'dsa': 'DSA', 'psa': 'PSA'}
"""The name of each type of result, as shown to the user."""

_RESULT_TABLES = {'dsa': 'dsa_single_metamodel', 'psa': 'psa_single_metamodel'}

_SHEET_NAME_MAX = 31
_SHEET_NAME_INVALID = re.compile(r'[\[\]:*?/\\]')

def metamodel_to_config_file(mm: NewsegsMetaModel) -> dict[str, Any]:
    """
    Encapsulate a model and finance configuration in a dictionary.
    """

    odict = {
        'config_name': mm.name,
        'metamodel': mm.to_dict_repr(),
    }
    return odict

@dataclass
class ResultsExport:
    """The download of the results of configurations, and which configurations it holds.

    Attributes:
        download: The data for a `dcc.Download`, or None if no configuration has results.
        exported: Names of the configurations whose results are in the download.
        missing: Names of the configurations without results, which were left out.
    """
    download: dict[str, Any] | None = None
    exported: list[str] = field(default_factory = list)
    missing: list[str] = field(default_factory = list)

def _get_metamodel_deterministic_raw_data(metamodel: NewsegsMetaModel) -> pd.DataFrame | None:
    """The deterministic results of a metamodel, whose results have been reattached, as one frame; None if it has none."""
    try:
        results = [
            metamodel.model.get_generation_result(),
            metamodel.model.get_grid_result(),
            metamodel.model.get_consumption_storage_result(),
        ]
    except AttributeError:
        return None

    all_frames = []
    for res in results:
        if res is None:
            continue
        all_frames += [res.meters_to_pandas(), res.dsm_to_pandas()]

    all_frames = [x for x in all_frames if not x.empty]
    if not all_frames:
        return None

    odf = all_frames[0]
    for frame in all_frames[1:]:
        odf = odf.join(frame)
    return odf

def get_result_frame(
    result_type: ResultType,
    metamodel: NewsegsMetaModel,
    result_provider: NewsegsResultProviderInterface,
) -> pd.DataFrame | None:
    """The results of a type for a metamodel, as stored; stale results are included.

    Args:
        result_type: The type of analysis: `det`, `dsa` or `psa`.
        metamodel: The metamodel.
        result_provider: Provider of results.

    Returns:
        The results, or None if the metamodel has none.
    """
    match result_type:
        case 'det':
            metamodel.model.reattach_results(result_provider)
            return _get_metamodel_deterministic_raw_data(metamodel)
        case 'dsa' | 'psa':
            result_data, _ = result_provider.get_result(_RESULT_TABLES[result_type], metamodel.table_config, True)
            if result_data is None:
                return None
            assert isinstance(result_data, pd.DataFrame)
            return result_data
        case _:
            raise ValueError(f'result_type not recognised: {result_type}')

def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    """The frame without time zones on its index and datetime columns, which Excel can't hold."""
    index = df.index
    tz_columns = [c for c in df.columns if getattr(df[c].dtype, 'tz', None) is not None]
    if getattr(index, 'tz', None) is None and not tz_columns:
        return df
    df = df.copy()
    if getattr(index, 'tz', None) is not None:
        df.index = index.tz_localize(None) # pyright: ignore[reportAttributeAccessIssue]
    for c in tz_columns:
        df[c] = df[c].dt.tz_localize(None)
    return df

def sheet_names(names: Sequence[str]) -> list[str]:
    """Names of worksheets for the names given: valid in Excel, and unique.

    Characters that Excel does not allow are replaced, names are cut to 31 characters, and a name that is taken
    (ignoring case, as Excel does) is numbered.

    Args:
        names: The names, e.g. of configurations.

    Returns:
        The sheet names, in the same order.
    """
    taken: set[str] = set()
    out = []
    for name in names:
        base = _SHEET_NAME_INVALID.sub('_', str(name)).strip().strip("'") or 'Sheet'
        candidate = base[:_SHEET_NAME_MAX]
        n = 1
        while candidate.lower() in taken:
            n += 1
            suffix = f' ({n})'
            candidate = base[:_SHEET_NAME_MAX - len(suffix)] + suffix
        taken.add(candidate.lower())
        out.append(candidate)
    return out

def _unique_file_stubs(names: Sequence[str]) -> list[str]:
    """File names (without extension) for the names given: valid, and unique."""
    taken: set[str] = set()
    out = []
    for name in names:
        base = pathvalidate.sanitize_filename(str(name)) or 'configuration'
        candidate = base
        n = 1
        while candidate.lower() in taken:
            n += 1
            candidate = f'{base} ({n})'
        taken.add(candidate.lower())
        out.append(candidate)
    return out

def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv().encode('utf-8')

def _xlsx_bytes(frames: Sequence[pd.DataFrame], names: Sequence[str]) -> bytes:
    buffer = io.BytesIO()
    # xlsxwriter writes the deterministic results of a configuration in about two thirds of the time of openpyxl
    with pd.ExcelWriter(buffer, engine = 'xlsxwriter') as writer:
        for df, sheet in zip(frames, sheet_names(names)):
            # Unmerged index cells, so that every row of a multi-level index reads back with its labels
            _strip_tz(df).to_excel(writer, sheet_name = sheet, merge_cells = False)
    return buffer.getvalue()

def _config_json(mm: NewsegsMetaModel) -> str:
    # As the DSA and PSA uploads read it: the metamodel itself
    return json.dumps(mm.to_dict_repr(), cls = jsonfuncs.NumpyEncoder, sort_keys = False, indent = 4)

def build_download(
    result_type: ResultType,
    results: Sequence[tuple[str, pd.DataFrame]],
    format_option: FormatOption,
    project_name: str,
    configurations: Sequence[NewsegsMetaModel] = (),
) -> dict[str, Any]:
    """The data for a `dcc.Download` of the results of configurations.

    Args:
        result_type: The type of analysis: `det`, `dsa` or `psa`.
        results: The name of each configuration, and its results.
        format_option: `csv` or `xlsx`.
        project_name: Name of the project, which names the download of several configurations.
        configurations: Configurations to include as json; none to leave them out.

    Returns:
        The data for the download.
    """
    if format_option not in ('csv', 'xlsx'):
        raise ValueError(f'format_option not recognised: {format_option}')
    if not results:
        raise ValueError('No results to download')

    names = [name for name, _ in results]
    frames = [df for _, df in results]
    stubs = _unique_file_stubs(names)
    suffix = f'-{result_type}-results'

    if len(results) == 1:
        download_stub = stubs[0] + suffix
    else:
        download_stub = (pathvalidate.sanitize_filename(project_name) or 'project') + suffix

    # The files of the results
    files: list[tuple[str, bytes]]
    if format_option == 'xlsx':
        files = [(f'{download_stub}.xlsx', _xlsx_bytes(frames, names))]
    else:
        files = [(f'{stub}{suffix}.csv', _csv_bytes(df)) for stub, df in zip(stubs, frames)]

    if len(files) == 1 and not configurations:
        file_name, content = files[0]
        return dcc.send_bytes(content, filename = file_name)

    config_stubs = _unique_file_stubs([mm.name for mm in configurations])
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode = 'w', compression = zipfile.ZIP_DEFLATED) as archive:
        for file_name, content in files:
            archive.writestr(file_name, content)
        for stub, mm in zip(config_stubs, configurations):
            archive.writestr(f'{stub}-config.json', _config_json(mm))
    return dcc.send_bytes(zip_buffer.getvalue(), filename = f'{download_stub}.zip')

def export_results(
    result_type: ResultType,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    project_id: str,
    metamodel_ids: Sequence[str] | None = None,
    format_option: FormatOption = 'csv',
    include_configuration: bool = False,
) -> ResultsExport:
    """Export the results of a deterministic run, DSA or PSA of configurations of a project.

    Configurations without results are left out. Raises `KeyError` if a metamodel is not in the project.

    Args:
        result_type: The type of analysis: `det`, `dsa` or `psa`.
        project_provider: Provider of projects, metamodels and variables.
        result_provider: Provider of results.
        project_id: Id of the project.
        metamodel_ids: Ids of the metamodels, in the order to export them; by default the focussed one.
        format_option: `csv` or `xlsx`.
        include_configuration: Whether to include each configuration exported, as json.

    Returns:
        The download, and the configurations exported and left out.
    """
    if result_type not in RESULT_TYPE_LABELS:
        raise ValueError(f'result_type not recognised: {result_type}')

    proj = project_provider.get_project(project_id)
    if metamodel_ids is None:
        metamodel_ids = [project_provider.get_focussed_metamodel_id(project_id)]

    rval = ResultsExport()
    results: list[tuple[str, pd.DataFrame]] = []
    exported_mms: list[NewsegsMetaModel] = []
    for mm_id in metamodel_ids:
        mm = proj.get_metamodel_by_id(mm_id)
        frame = get_result_frame(result_type, mm, result_provider)
        if frame is None or frame.empty:
            rval.missing.append(mm.name)
            continue
        results.append((mm.name, frame))
        exported_mms.append(mm)
        rval.exported.append(mm.name)

    if not results:
        return rval

    rval.download = build_download(
        result_type,
        results,
        format_option,
        project_name = proj.name,
        configurations = exported_mms if include_configuration else (),
    )
    logger.info(
        'Exported %s results of project %s as %s. Configurations: %s; Without results: %s; Configuration included: %s',
        result_type, project_id, format_option, rval.exported, rval.missing, include_configuration,
    )
    return rval
