import os
from pathlib import Path
import time
from sqlalchemy.exc import OperationalError
import sys
from typing import Any, Callable, Optional, override
import uuid

from cachetools import LRUCache
import numpy as np
import pandas as pd
import sqlalchemy as sa

from newsegsmodelapp.components.result_file import load_result, save_result
from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightDataHoldingNewsegsComponent
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
            parent_component: NewsegsComponent | LightweightDataHoldingNewsegsComponent,
            request: Optional[RunRequest] = None,
            revision: Optional[int] = None,
        ):
        revision = parent_component.revision if revision is None else revision
        if isinstance(parent_component, NewsegsComponent):
            odict = dict(
                component_config_id = parent_component.id,
                component_type = parent_component.component_type,
                component_class = parent_component.__class__.__name__,
                component_version = parent_component.version,
                component_config_revision = revision,
                result_type = result_type
            )
        elif isinstance(parent_component, LightweightDataHoldingNewsegsComponent):
            odict = dict(
                component_config_id = parent_component.id,
                component_type = parent_component.component_type,
                component_class = parent_component.component_class,
                component_version = parent_component.component_version,
                component_config_revision = revision,
                result_type = result_type
            )
        else:
            raise TypeError(f'parent_component should by NewsegsComponent or LightweightDataholdingNewsegsComponent; is {type(parent_component)}')
        
        if request:
            if request.trigger_run_id != -1:
                # By default, store results with the inciting run id of the chain
                odict['run_id'] = request.trigger_run_id
            else:
                odict['run_id'] = request.run_id
        return odict

    @override
    def upsert_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent | str,
        result_object: object,
        mark_stale: bool = False,
        request: Optional[RunRequest] = None,
        revision: Optional[int] = None,
    ):
        
        result_details = self._result_to_table_data(
            result_type, 
            parent_component, 
            request = request,
            revision = revision,
        )
        if mark_stale:
            # Just knock the revision down a level for now
            result_details['component_config_revision'] = result_details['component_config_revision'] - 1 # pyright: ignore[reportOperatorIssue]

        # Try to save out the result object
        filename_root = self._result_store / ('res-' + str(uuid.uuid4()))
        saved_path = save_result(result_object, filename_root)

        result_details['result_file'] = saved_path

        stmt = self._table.insert().values(result_details)
        n_retries = 5
        success = False
        while n_retries > 0 and not success:
            try:
                with self._get_engine().begin() as conn:
                    conn.execute(stmt)
                success = True
            except OperationalError:
                time.sleep (0.1)
                n_retries -= 1

        if not success:
            raise ValueError(f'Result of {result_details['result_type']} saved to {saved_path}, but not uploaded to database')

        print (f'SAVED RESULT of type {result_details['result_type']} attached to {result_details['component_type']} with id {result_details['component_config_id']}, revision {result_details['component_config_revision']}')

    @override
    def get_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent | str,
        allow_stale: bool = True,
        revision: Optional[int] = None,
    ) -> tuple[Any, int] | tuple[None, None]:
        
        stmt = (
            sa.select(
                self._table.c.result_id,
                self._table.c.created_at,
                self._table.c.result_file,
                self._table.c.component_config_revision,
            )
            .where(self._table.c.result_type == result_type)
        )
        if isinstance(parent_component, str):
            stmt = stmt.where(self._table.c.component_config_id == parent_component)
        else:
            stmt = stmt.where(self._table.c.component_config_id == parent_component.id)
            
        stmt = stmt.order_by(self._table.c.created_at.desc())

        if revision is None:
            if not isinstance(parent_component, str):
                revision = parent_component.revision
            
        if not allow_stale:
            if revision is None:
                raise ValueError(f'If stale results are not allowed, the parent component or a nominated revision must be provided.')
            stmt = stmt.where(self._table.c.component_config_revision == revision)

        file_name = None
        with self._get_engine().connect() as conn:
            result = conn.execute(stmt)
            for idx, row in enumerate(result):
                if idx == 0:
                    file_name = row.result_file
                    rrs = row.component_config_revision
                if row.component_config_revision == revision:
                    if idx != 0:
                        file_name = row.result_file
                        rrs = revision
                    break

        if file_name is None:
            return None, None

        try:
            obj = load_result(Path(file_name))
        except FileNotFoundError:
            with self._get_engine().begin() as conn:
                conn.execute(sa.delete(self._table).where(self._table.c.result_file == file_name))
            return None, None
        
        return (obj, rrs)

    @override
    def get_run_result(
        self, 
        result_type: str, 
        run_id: int, 
        parent_component: Optional[NewsegsComponent | str] = None
    ) -> tuple[Any, int] | tuple[None, None]:
        stmt = (
            sa.select(
                self._table.c.result_id,
                self._table.c.result_file,
                self._table.c.component_config_revision,
            )
            .where(self._table.c.result_type == result_type)
            .where(self._table.c.run_id == run_id)
        )
        if parent_component:
            if isinstance(parent_component, str):
                stmt = stmt.where(self._table.c.component_config_id == parent_component)
            else:    
                stmt = stmt.where(self._table.c.component_config_id == parent_component.id)

        with self._get_engine().connect() as conn:
            res = conn.execute(stmt)
        if not res:
            return None, None
        result_rows = {row["result_id"]: dict(row) for row in res.mappings()}
        if len(result_rows) == 0:
            return None, None
        
        res_id = next(iter(result_rows))
        file_name = result_rows[res_id]['result_file']
        rrs = result_rows[res_id]['component_config_revision']

        try:
            obj = load_result(Path(file_name))
        except FileNotFoundError:
            with self._get_engine().begin() as conn:
                conn.execute(sa.delete(self._table).where(self._table.c.result_file == file_name))
            return None, None

        return (obj, rrs)

    def result_exists(
        self,
        result_type: str,
        run_id: int,
        parent_component: NewsegsComponent | str,
        revision: Optional[int] = None,
    ) -> str | bool:
        stmt = (
            sa.select(
                self._table.c.result_id,
                self._table.c.result_file,
                self._table.c.component_config_revision,
            )
            .where(
                self._table.c.result_type == result_type
            )
        )
        if isinstance(parent_component, str):
            stmt = stmt.where(
                self._table.c.component_config_id == parent_component
            )
        else:
            stmt = stmt.where(
                self._table.c.component_config_id == parent_component.id
            )

        if run_id != -1:
            stmt = stmt.where(
                self._table.c.run_id == run_id
            )
        elif revision is not None:
            stmt = stmt.where(
                self._table.c.component_config_revision == revision
            )
        elif isinstance(parent_component, NewsegsComponent):
            stmt = stmt.where(
                self._table.c.component_config_revision == parent_component.revision
            )

        with self._get_engine().connect() as conn:
            result = conn.execute(stmt).fetchall()

        for res in result:
            if not os.path.exists(res.result_file):
                with self._get_engine().begin() as conn:
                    conn.execute(sa.delete(self._table).where(self._table.c.result_file == res.result_file))
                continue
            return res.result_id
        
        return False            
        
class CachedFromDatabaseResultProvider(
    FromDatabaseResultProvider
):
    
    def __init__(self, get_engine: Callable[[], sa.Engine], result_store: Path):
        super().__init__(get_engine, result_store)
        self._result_cache = LRUCache(maxsize = 128)
        self._run_to_revision_lookup = LRUCache(maxsize = 128)

    @override
    def get_result(
        self, 
        result_type: str, 
        parent_component: NewsegsComponent | str,
        allow_stale: bool = True,
        revision: Optional[int] = None,
    ) -> tuple[Any, int] | tuple[None, None]:

        if isinstance(parent_component, str):
            result_key = (result_type, parent_component, revision)
        else:
            if revision is None:
                result_key = (result_type, parent_component.id, parent_component.revision)
            else:
                result_key = (result_type, parent_component.id, revision)
        
        print(f'FINDING RESULT {result_key}')
        if result_key in self._result_cache:
            print(f'RETURNING RESULT FROM CACHE {result_key}')
            return self._result_cache[result_key], result_key[2] # pyright: ignore[reportReturnType]

        print(f'RETURNING RESULT FROM STORE {result_key}')
        obj, rrs = super().get_result(
            result_type, parent_component, allow_stale, revision
        )
        if obj is None:
            print(f'NOT ADDING TO CACHE AS NO RESULT - {result_key}')
        if rrs is None or rrs != result_key[2]:
            print(f'NOT ADDING TO CACHE AS STALE - {result_key} - available revision is {rrs}')
        if obj is not None and rrs == result_key[2]:
            print(f'ADDING TO CACHE - {result_key}')
            self._result_cache[result_key] = obj
        return (obj, rrs) # pyright: ignore[reportReturnType]

    @override
    def get_run_result(
        self, 
        result_type:str,
        run_id: int,
        parent_component: Optional[NewsegsComponent | str] = None
    ) -> tuple[Any, int] | tuple[None, None]:
        if isinstance(parent_component, str):
            rrl_key = (result_type, run_id, parent_component)
        elif isinstance(parent_component, NewsegsComponent):
            rrl_key = (result_type, run_id, parent_component.id)
        else:
            rrl_key = (result_type, run_id, None)

        if rrl_key in self._run_to_revision_lookup:
            result_key = self._run_to_revision_lookup[rrl_key]
            if result_key in self._result_cache:
                return self._result_cache[result_key], result_key[2]

        obj, rrs = super().get_run_result(result_type, run_id, parent_component)

        if obj is None:
            return (None, None)

        if isinstance(parent_component, str):
            result_key = (result_type, rrs, parent_component)
        elif isinstance(parent_component, NewsegsComponent):
            result_key = (result_type, rrs, parent_component.id)
        else:
            result_key = (result_type, rrs, None)

        self._result_cache[result_key] = obj

        return (obj, rrs)
    