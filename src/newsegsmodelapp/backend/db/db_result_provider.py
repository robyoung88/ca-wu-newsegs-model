from pathlib import Path
from typing import Any, Callable, Optional, override
import uuid

from cachetools import LRUCache
import numpy as np
import pandas as pd
import sqlalchemy as sa

from newsegsmodelapp.components.result_file import load_result, save_result
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelapp.registers import RunRequest
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface

from cachetools import LRUCache

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
        mark_stale: bool = False,
        request: Optional[RunRequest] = None,
    ):
        result_details = self._result_to_table_data(result_type, parent_component, request = request)
        if mark_stale:
            # Just knock the revision down a level for now
            result_details['component_config_revision'] = result_details['component_config_revision'] - 1 # pyright: ignore[reportOperatorIssue]

        # Try to save out the result object
        filename_root = self._result_store / ('res-' + str(uuid.uuid4()))
        saved_path = save_result(result_object, filename_root)

        result_details['result_file'] = saved_path

        stmt = self._table.insert().values(result_details)
        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        print (f'SAVED RESULT of type {result_details['result_type']} attached to {result_details['component_type']} with id {result_details['component_config_id']}, revision {result_details['component_config_revision']}')

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
            .order_by(self._table.c.created_at)
        )

        revision = parent_component.revision
        if not allow_stale:
            stmt = stmt.where(self._table.c.component_config_revision == revision)

        with self._get_engine().connect() as conn:
            odf = pd.read_sql(stmt, conn)

        if len(odf):
            if np.any(odf['component_config_revision'] == revision):
                file_name = odf.loc[odf['component_config_revision'] == revision, 'result_file'].iloc[-1]
                rrs = revision
            else:
                #odf = odf.sort_values('created_at')
                file_name = odf['result_file'].iloc[-1]
                rrs = odf['component_config_revision'].iloc[-1]

            try:
                obj = load_result(Path(file_name))
            except FileNotFoundError:
                with self._get_engine().begin() as conn:
                    conn.execute(sa.delete(self._table).where(self._table.c.result_file == file_name))
                return None, None
            
            return (obj, rrs)

        return None, None

class CachedFromDatabaseResultProvider(
    FromDatabaseResultProvider
):
    
    def __init__(self, get_engine: Callable[[], sa.Engine], result_store: Path):
        super().__init__(get_engine, result_store)
        self._result_cache = LRUCache(maxsize = 64)

    @override
    def get_result(self, result_type: str, parent_component: NewsegsComponent, allow_stale: bool = True) -> tuple[Any, int] | tuple[None, None]:

        result_key = (result_type, parent_component.id, parent_component.revision)
        print(f'FINDING RESULT {result_key}')
        if result_key in self._result_cache:
            print(f'RETURNING RESULT FROM CACHE {result_key}')
            return self._result_cache[result_key], result_key[2] # pyright: ignore[reportReturnType]

        obj, rrs = super().get_result(result_type, parent_component, allow_stale)
        if obj is None:
            print(f'NOT ADDING TO CACHE AS NO RESULT - {result_key}')
        if rrs is None or rrs != result_key[2]:
            print(f'NOT ADDING TO CACHE AS STALE - {result_key} - available revision is {rrs}')
        if obj is not None and rrs == result_key[2]:
            print(f'ADDING TO CACHE - {result_key}')
            self._result_cache[result_key] = obj
        return (obj, rrs) # pyright: ignore[reportReturnType]
    