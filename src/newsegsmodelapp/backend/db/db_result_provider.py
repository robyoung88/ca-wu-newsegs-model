"""Providers of results: the database table of results and the results store on disk.
"""
import logging
logger = logging.getLogger(__name__)

import os
from pathlib import Path
from sqlalchemy.exc import OperationalError
from typing import Any, Callable, Optional, override
import uuid

from cachetools import LRUCache
import sqlalchemy as sa

from newsegsmodelapp.backend.db.db import read_transaction, write_transaction, write_with_retries
from newsegsmodelapp.components.result_file import load_result, save_result
from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightDataHoldingNewsegsComponent, LightweightNewsegsComponent
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelapp.registers import RunRequest
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface

from cachetools import LRUCache

class FromDatabaseResultProvider(NewsegsResultProviderInterface):
    """Provider of the results of runs, from the results table and the results store.

    The database holds the metadata (the component and revision the result belongs to, and the request and run that produced it) and the path of
    the file; the data are in the results store on disk.

    Args:
        get_engine: Function returning the SQLAlchemy engine.
        result_store: Directory of the results store.
    """
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
            odict['run_id'] = request.run_id
            if request.trigger_request_id != -1:
                # By default, store results with the inciting run id of the chain
                odict['request_id'] = request.trigger_request_id
            else:
                odict['request_id'] = request.request_id
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
        if request:
            logger.debug(
                'Saving Result: Type = %s; Request ID: %d; Process Run ID = %d; '
                'Triggering Request ID = %d; Attached to Component ID = %s; revision = %d;',
                result_details['result_type'], request.request_id, request.run_id, request.trigger_request_id,
                result_details['component_config_id'], result_details['component_config_revision']
            )
        else:
            logger.debug(
                'Saving Result: Type = %s; Attached to Component ID = %s; revision = %d; '
                '- no request details provided',
                result_details['result_type'], result_details['component_config_id'], 
                result_details['component_config_revision']
            )   
        try:
            write_with_retries(self._get_engine(writer = True), stmt)
            success = True
        except OperationalError:
            success = False
        
        if not success:
            raise ValueError(f'Result of {result_details['result_type']} saved to {saved_path}, but not uploaded to database')

        if request:
            logger.info(
                'Result saved: Type = %s; Request ID = %d; Process Run ID = %d; ' 
                'Triggering Request ID = %d; Attached to Component ID = %s; revision = %d; Filename = %s;',
                result_details['result_type'], request.request_id, request.run_id, request.trigger_request_id,
                result_details['component_config_id'], result_details['component_config_revision'], saved_path
            )
        else:
            logger.info(
                'Result saved: Type = %s; Attached to Component ID = %s; revision = %d; '
                '- no request details provided. Filename = %s ',
                result_details['result_type'], result_details['component_config_id'],
                result_details['component_config_revision'], saved_path,
            )           
             
    def duplicate_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent | LightweightNewsegsComponent,
        new_request: RunRequest
    ):
        """Duplicate a result row in response to a new request providing the same data"""
        if new_request.trigger_request_id != -1:
            new_request_id = new_request.trigger_request_id
        else:
            new_request_id = new_request.request_id

        # 1. Define columns to insert (excluding auto-increment primary key 'id')
        insert_cols = [c for c in self._table.c if c.name != 'result_id']

        # 2. Select the latest matching row as a subquery
        latest_subq = (
            sa.select(self._table)
            .where(
                sa.and_(
                    self._table.c.result_type == result_type,
                    self._table.c.component_config_revision == parent_component.revision,
                    self._table.c.component_config_id == parent_component.id
                )
            )
            .order_by(self._table.c.result_id.desc())
            .limit(1)
            .subquery()
        )

        # 3. Build the SELECT expression, substituting run_id with the new literal
        select_stmt = sa.select(
            *[
                sa.literal(new_request_id).label('request_id') if c.name == 'request_id' else latest_subq.c[c.name]
                for c in insert_cols
            ]
        )

        # 4. Execute the INSERT ... SELECT statement
        insert_stmt = self._table.insert().from_select(
            [c.name for c in insert_cols],
            select_stmt
        )

        logger.debug(
            'Duplicating result of type %s attached to Component ID = %s; with revision = %d; '
            'for Request ID = %d;',
            result_type, parent_component.id, parent_component.revision, new_request_id
        )
        with write_transaction(self._get_engine(writer = True)) as conn:
            conn.execute(insert_stmt)
        logger.info(
            'Duplicated result of type %s attached to Component ID = %s; with revision = %d; '
            'for Request ID = %d;',
            result_type, parent_component.id, parent_component.revision, new_request_id
        )

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
            
        stmt = stmt.order_by(
            self._table.c.component_config_revision,
            self._table.c.created_at.desc()
        )

        if revision is None:
            if not isinstance(parent_component, str):
                revision = parent_component.revision
            
        if not allow_stale:
            if revision is None:
                raise ValueError(f'If stale results are not allowed, the parent component or a nominated revision must be provided.')
            stmt = stmt.where(self._table.c.component_config_revision == revision)

        file_name = None
        with read_transaction(self._get_engine()) as conn:
            result = conn.execute(stmt)
            for idx, row in enumerate(result):
                logger.debug(
                    'Iterating results [%d]: Type = %s; Parent = %s; Revision = %s; Created at: %s',
                    idx, result_type, parent_component.id, row.component_config_revision, row.created_at
                )
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
            with write_transaction(self._get_engine(writer = True)) as conn:
                conn.execute(sa.delete(self._table).where(self._table.c.result_file == file_name))
            return None, None
        
        return (obj, rrs)

    @override
    def get_request_result(
        self, 
        result_type: str, 
        request_id: int, 
        parent_component: Optional[NewsegsComponent | str] = None
    ) -> tuple[Any, int] | tuple[None, None]:
        stmt = (
            sa.select(
                self._table.c.result_id,
                self._table.c.result_file,
                self._table.c.component_config_revision,
            )
            .where(self._table.c.result_type == result_type)
            .where(self._table.c.request_id == request_id)
        )
        if parent_component:
            if isinstance(parent_component, str):
                stmt = stmt.where(self._table.c.component_config_id == parent_component)
            else:    
                stmt = stmt.where(self._table.c.component_config_id == parent_component.id)

        with read_transaction(self._get_engine()) as conn:
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
            with write_transaction(self._get_engine(writer = True)) as conn:
                conn.execute(sa.delete(self._table).where(self._table.c.result_file == file_name))
            return None, None

        return (obj, rrs)

    def get_result_by_id(
        self,
        result_id: int
    ) ->  tuple[Any, int] | tuple[None, None]:
        """Get a result by its id.

        Args:
            result_id: Id of the result.

        Returns:
            The result and the revision of the component it was calculated for; `(None, None)` if there is no such result.
        """
        stmt = (
            sa.select(self._table.c.result_file, self._table.c.component_config_revision)
            .where(self._table.c.result_id == result_id)
        )

        with read_transaction(self._get_engine()) as conn:
            row = conn.execute(stmt).fetchone()
        
        if not row:
            return None, None

        try:
            obj = load_result(Path(row.result_file))
        except FileNotFoundError:
            return None, None
        
        return (obj, row.component_config_revision)

    def result_exists(
        self,
        result_type: str,
        request_id: int,
        parent_component: NewsegsComponent | LightweightNewsegsComponent | str,
        revision: Optional[int] = None,
    ) -> int | bool:
        """Whether a result exists for a component, request and type.

        If a revision is given, the result must be for that revision.

        Args:
            result_type: Type of the result.
            request_id: Id of the request.
            parent_component: The component (or its id) that the result belongs to.
            revision: Revision of the component that the result was calculated for; any revision if None.

        Returns:
            The id of the result if there is one, otherwise False.
        """
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

        if request_id != -1:
            stmt = stmt.where(
                self._table.c.request_id == request_id
            )
        elif revision is not None:
            stmt = stmt.where(
                self._table.c.component_config_revision == revision
            )
        elif isinstance(parent_component, (NewsegsComponent, LightweightNewsegsComponent)):
            stmt = stmt.where(
                self._table.c.component_config_revision == parent_component.revision
            )

        with read_transaction(self._get_engine()) as conn:
            result = conn.execute(stmt).fetchall()

        for res in result:
            if not os.path.exists(res.result_file):
                with write_transaction(self._get_engine(writer = True)) as conn:
                    conn.execute(sa.delete(self._table).where(self._table.c.result_file == res.result_file))
                continue
            return res.result_id
        
        return False

         
class CachedFromDatabaseResultProvider(
    FromDatabaseResultProvider
):
    
    """A `FromDatabaseResultProvider` which keeps recently loaded results in an LRU cache, so that results displayed repeatedly are not read from disk each time.
    """
    def __init__(self, get_engine: Callable[[], sa.Engine], result_store: Path):
        super().__init__(get_engine, result_store)
        self._result_cache = LRUCache(maxsize = 128)
        self._run_to_revision_lookup = LRUCache(maxsize = 128)

    @override
    def get_result(
        self, 
        result_type: str, 
        parent_component: NewsegsComponent | LightweightNewsegsComponent | str,
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

        logger.debug(
            'Finding result: Type = %s, Parent = %s, Revision = %s',
            *result_key
        )
        if result_key in self._result_cache:
            logger.debug(
                'Returning result: Type = %s, Parent = %s, Revision = %s from cache',
                *result_key
            )
            return self._result_cache[result_key], result_key[2] # pyright: ignore[reportReturnType]

        obj, rrs = super().get_result(
            result_type, parent_component, allow_stale, revision
        )
        if obj is None:
            logger.debug(
                'Unable to find result: Type = %s, Parent = %s, Revision = %s',
                *result_key
            )
        if rrs is None or rrs != result_key[2]:
            logger.debug(
                'Returning stale result for: Type = %s, Parent = %s, Revision = %s - provided revision is %s;',
                *result_key, rrs
            )
        if obj is not None and rrs == result_key[2]:
            logger.debug(
                'Returning result: Type = %s, Parent = %s, Revision = %s from store',
                *result_key
            )
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
    