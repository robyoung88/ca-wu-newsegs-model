from pathlib import Path
from typing import Any, Callable, Optional, override
import uuid

import pandas as pd
import sqlalchemy as sa

from newsegsmodelapp.components.result_file import load_result, save_result
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelapp.registers import RunRequest
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface


class FromDatabaseResultProvider(NewsegsResultProviderInterface):
    def __init__(
        self,
        get_engine: Callable[[], sa.Engine],
        result_store: Path
    ):
        self._get_engine = get_engine
        self._result_store = result_store
        self._table = tbls.results

    
    def _result_to_table_data(
            self, 
            result_type: str,
            parent_component: NewsegsComponent,
            request: Optional[RunRequest] = None,
        ):
        odict = dict(
            component_config_id = parent_component.id,
            component_type = parent_component.component_type,
            component_class = parent_component.__class__.__name__,
            component_version = parent_component.version,
            component_config_revision = parent_component.revision,
            result_type = result_type
        )
        if request:
            odict['run_id'] = request.run_id
        return odict

    @override
    def upsert_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent,
        result_object: object,
        request: Optional[RunRequest] = None,
    ):
        result_details = self._result_to_table_data(result_type, parent_component, request = request)

        # Try to save out the result object
        filename_root = self._result_store / ('res-' + str(uuid.uuid4()))
        saved_path = save_result(result_object, filename_root)

        result_details['result_file'] = saved_path

        stmt = self._table.insert().values(result_details)
        with self._get_engine().begin() as conn:
            conn.execute(stmt)

    def get_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent,
        allow_stale: bool = True
    ) -> tuple[Any, int] | tuple[None, None]:
        stmt = (
            sa.select(
                self._table.c.result_id,
                self._table.c.created_at,
                self._table.c.result_file,
                self._table.c.component_config_revision,
            )
            .where(self._table.c.result_type == result_type)
            .where(self._table.c.component_config_id == parent_component.id)
        )

        revision = parent_component.revision
        if not allow_stale:
            stmt = stmt.where(self._table.c.component_config_revision == revision)

        with self._get_engine().connect() as conn:
            odf = pd.read_sql(stmt, conn)

        if len(odf):
            if revision in odf['component_config_revision']:
                file_name = odf['result_file'].loc[odf['component_config_revision'] == revision][0]
                rrs = revision
            else:
                odf = odf.sort_values('created_at')
                file_name = odf['result_file'].iloc[-1]
                rrs = odf['component_config_revision'].iloc[-1]

            obj = load_result(Path(file_name))
            return (obj, rrs)

        return None, None
        