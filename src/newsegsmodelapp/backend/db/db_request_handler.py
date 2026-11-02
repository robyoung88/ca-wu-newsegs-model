from dataclasses import asdict
import logging
logger = logging.getLogger(__name__)

import json
from typing import Callable, Optional, Sequence, overload, override

import sqlalchemy as sa

from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db import read_transaction, write_transaction, write_with_retries
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestHandlerInterface
from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelapp.registers import RunRequest
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

_REQUEST_REGISTERS = {
    'run': registers.RUN_REQUEST_REGISTER,
    'postprocess': registers.POSTPROCESS_REQUEST_REGISTER,
    'tabledraw': registers.TABLE_DRAW_REQUEST_REGISTER
}

_REQUEST_CLASSES = {
    'run': registers.RunRequest,
    'postprocess': registers.PostprocessRequest,
    'tabledraw': registers.TableDrawRequest,
}


class FromDatabaseRequestHandler(RequestHandlerInterface):
    def __init__(
        self,
        get_engine: Callable[[], sa.Engine],
    ):
        self._get_engine = get_engine
        self._table = tbls.requests

    @classmethod
    def _request_to_database_values(cls, request: RunRequest) -> dict:
        odict = asdict(request)
        # Remove request id, as this will either be assigned or used to match
        del odict['request_id']
        # Stringify payload
        if request.payload is not None:
            if isinstance(request.payload, object) and hasattr(request.payload, 'json_dumps'):
                odict['payload'] = request.payload.json_dumps()
            else:
                odict['payload'] = json.dumps(request.payload)
        return odict

    @classmethod
    def _database_row_to_request(cls, row: sa.Row) -> registers.RunRequest:
        request = registers.RunRequest.from_dict(row._mapping)
        if request.payload is not None:
            request.payload = json.loads(request.payload)
        return request

    @classmethod
    def _get_request_creator(
        cls,
        request_type: str,
        request_class: Optional[str] = None,
    ) -> tuple[Callable, str]:
        """The RunRequest creation function for a request type

        Args:
            request_type (str): Key for the request procedure type
            request_class (Optional[str], optional): Key for the request procedure class (e.g. 'run', 'postprocessing', 'table_draw'). Defaults to None.

        Raises:
            ValueError: If a request creation function cannot be found

        Returns:
            tuple[Callable, str]: (Request creation function, request_class)
        """
        if not request_class:
            # Try and find procedure name in all registers
            for proc_class, reg in _REQUEST_REGISTERS.items():
                get_req = reg.get(request_type)
                if get_req is not None:
                    return get_req, proc_class
            else:
                raise ValueError(f'Request type {request_type} not found.')
        else:
            reg = _REQUEST_REGISTERS[request_class]
            get_req = reg.get(request_type)
            if get_req is None:
                raise ValueError(f'Request type {request_type} not found in {request_class} request register. Available keys are {reg.keys()}.')
            return get_req, request_class

    @classmethod
    def _create_request(
        cls,
        request_type: str,
        request_class: str,
        get_runrequest_function: Callable,
        active_project_id: str,
        project_provider: NewsegsProjectProviderInterface,
        config: dict | None = None,
        triggering_request: RunRequest | None = None
    ) -> RunRequest:
        """_summary_

        Args:
            request_type (str): _description_
            request_class (str): _description_
            get_runrequest_function (Callable): _description_
            active_project_id (str): _description_
            project_provider (NewsegsProjectProviderInterface): _description_
            config (dict | None, optional): _description_. Defaults to None.
            triggering_request (RunRequest | None, optional): _description_. Defaults to None.

        Raises:
            ValueError: If request procedure class is not supported.

        Returns:
            RunRequest: _description_
        """
        match request_class:
            case 'run':
                request = get_runrequest_function(active_project_id, project_provider, config)
            case 'postprocess':
                if triggering_request is None:
                    triggering_request = registers.RUN_REQUEST_REGISTER['_dummyrequest'](
                        active_project_id, project_provider, config
                    )
                request = get_runrequest_function(triggering_request, config)
            case 'tabledraw':
                if triggering_request is None:
                    triggering_request = registers.RUN_REQUEST_REGISTER['_dummyrequest'](
                        active_project_id, project_provider, config
                    )
                request = get_runrequest_function(triggering_request, config)
            case _:
                raise ValueError(f'Request procedure class not recognised: {request_class}')
        return request

    @override
    def add_request(
        self, 
        request_type: str, 
        active_project_id: str, 
        project_provider: NewsegsProjectProviderInterface, 
        request_class: str | None = None, 
        config: dict | None = None, 
        triggering_request: RunRequest | None = None
    ) -> RunRequest:

        try:
            get_req, request_class = self._get_request_creator(request_type, request_class)
        except ValueError as e:
            raise ValueError(f'Request cannot be added - {e}')

        request = self._create_request(
            request_type, request_class, get_req, active_project_id,
            project_provider, config, triggering_request
        )

        insertion_data = self._request_to_database_values(request)
        
        stmt = (
            self._table.insert()
            .values(insertion_data)
        )

        with write_transaction(self._get_engine(writer = True)) as conn:
            res = conn.execute(stmt)
            if res and res.inserted_primary_key:
                request.request_id = res.inserted_primary_key[0]
                return request

        raise RuntimeError('Unable to generate a new request.')

    @overload
    def get_request(self, request_id: int) -> RunRequest:
        ...

    @overload
    def get_request(self, request_id: Sequence[int]) -> list[RunRequest]:
        ...

    @override
    def get_request(self, request_id: int | Sequence[int]) -> RunRequest | list[RunRequest]:
        if isinstance(request_id, int):
            request_id = [request_id]
            singular = True
        else:
            singular = False

        stmt = (
            self._table.select()
            .where(self._table.c.request_id.in_(request_id))
        )
        with read_transaction(self._get_engine()) as conn:
            rows = conn.execute(stmt).fetchall()
        request_mapping = {x.request_id: self._database_row_to_request(x) for x in rows}
        if singular:
            if not request_mapping:
                raise ValueError(f'Request ID not found: {request_id[0]}')
            return request_mapping[request_id[0]]
        requests = [request_mapping.get(x, None) for x in request_id]
        return requests

    @override
    def get_active_requests(
        self,
        active_project_id: str | None = None
    ) -> list[registers.RunRequest]:
        stmt = self._table.select().where(self._table.c.status.in_(['AWAITING DISPATCH', 'DISPATCHED']))
        if active_project_id:
            stmt = stmt.where(
                self._table.c.project_id == active_project_id
            )

        with read_transaction(self._get_engine()) as conn:
            rows = conn.execute(stmt).fetchall()
        return [self._database_row_to_request(x) for x in rows]

    @override
    def get_new_requests(
        self, 
        active_project_id: str|None = None
    ) -> list[registers.RunRequest]:
        
        stmt = (
            self._table.select()
            .where(self._table.c.status == 'AWAITING DISPATCH')
        )
        if active_project_id:
            stmt = stmt.where(
                self._table.c.project_id == active_project_id
            )

        with read_transaction(self._get_engine()) as conn:
            rows = conn.execute(stmt).fetchall()
        return [self._database_row_to_request(x) for x in rows]

    def set_request_status(
        self,
        request_id: int | Sequence[int],
        status: tbls.REQUEST_STATUS
    ):
        if isinstance(request_id, int):
            request_id = [request_id,]

        stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id.in_(request_id))
            .values(status = status)
        )
        write_with_retries(self._get_engine(writer = True), stmt)

    @override
    def mark_dispatched(
        self, 
        request_id: int | Sequence[int], 
        run_id: int | None | Sequence[int | None]
    ):
        if isinstance(request_id, int):
            request_id = [request_id,]

        if run_id is None:
            are_dispatched = [False] * len(request_id)
            run_id = [None] * len(request_id)
        elif isinstance(run_id, int):
            if len(request_id) != 1:
                raise ValueError('Single run id pass for multiple request ids')
            run_id = [run_id,]
            are_dispatched = [True,]
        else:
            are_dispatched = [not x is None for x in run_id]

        status = ['DISPATCHED' if x else 'AWAITING DISPATCH' for x in are_dispatched]

        data = [
            {'_id': id_, 'run_id_': r_id_, 'status_': status_}
            for id_, r_id_, status_ in zip(request_id, run_id, status)
        ]

        stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id == sa.bindparam("_id"))
            .values(
                status = sa.bindparam('status_'),
                run_id = sa.bindparam('run_id_'),
            )
        )

        write_with_retries(self._get_engine(writer = True), stmt, data)
        if logger.level <= logging.DEBUG:
            for rq_id, rn_id in zip(request_id, run_id):
                logger.debug('Marked as DISPATCHED: Request ID = %d; Run ID = %d;', rq_id, rn_id)

    @override
    def mark_completed(self, request_id: int | Sequence[int], completed: bool = True):
        if isinstance(request_id, int):
            request_id = [request_id,]

        stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id.in_(request_id))
            .values(status = 'FULFILLED')
        )
        
        write_with_retries(self._get_engine(writer = True), stmt)
        if logger.level <= logging.DEBUG:
            for rq_id in request_id:
                logger.debug('Marked as FULFILLED: Request ID = %d;', rq_id)

    @override
    def increment_failure(self, request_id: int) -> bool:
        incr_stmt = (
            sa.update(self._table)
            .where(
                self._table.c.request_id == request_id,
                self._table.c.status != 'CANCELLED',
            )
            .values(
                run_id = None,
                retry_number = self._table.c.retry_number + 1,
                status = sa.case(
                    (self._table.c.retry_number + 1 < self._table.c.max_retries, 'AWAITING DISPATCH'),
                    else_='CANCELLED'
                ),
            )
            .returning(self._table.c.retry_number < self._table.c.max_retries)
        )

        with write_transaction(self._get_engine(writer = True)) as conn:
            res = conn.execute(incr_stmt)
            if res:
                ok_retry = res.scalar()
                if ok_retry is not None:
                    if ok_retry:
                        logger.info('Request %s is ok to retry after incrementing attempt counter', request_id)
                    else:
                        logger.info('Request %s will not be retried after incrementing attempt counter', request_id)
                    return ok_retry
                else:
                    logger.info('Request %s will not be retried after incrementing attempt counter', request_id)
                    return False

        return False

    def cancel_requests(
        self, request_id: Optional[int | Sequence[int]] = None, chain: bool = True
    ) -> list[int]:
        """Cancel requests, also cancelling any associated runs.
        
        If a request_id is not provided, cancels all active requests.
        If chain, then all requests triggered by requests in the provided list
        are also cancelled.
        """
        
        select_requests = (
            sa.select(
                self._table.c.request_id,
                self._table.c.run_id
            )
            .where(
                self._table.c.status.in_([
                    'AWAITING DISPATCH',
                    'DISPATCHED',
                ])
            )
        )
        if request_id is not None:
            request_id = [request_id] if isinstance(request_id, int) else request_id

            if chain:
                select_requests = (
                    select_requests
                    .where(
                        sa.or_(
                            self._table.c.request_id.in_(request_id),
                            self._table.c.trigger_request_id.in_(request_id))
                    )
                )
            else:
                select_requests = (
                    select_requests
                    .where(self._table.c.request_id.in_(request_id))
                )

        # Filters must be applied to the select before it becomes a subquery, as
        # a subquery is a FROM clause with no .where. Selecting from the subquery
        # (a derived table) also stops it correlating with the requests table
        # updated below, which would otherwise drop its FROM clause.
        requests_to_cancel = select_requests.subquery()

        run_cancel_statement = (
            sa.update(tbls.runs)
            .where(
                tbls.runs.c.run_id.in_(
                    sa.select(requests_to_cancel.c.run_id)
                    .where(requests_to_cancel.c.run_id >= 0)
                )
            )
            .values(cancel_requested = True)
        )

        request_cancel_statement = (
            sa.update(self._table)
            .where(
                self._table.c.request_id.in_(
                    sa.select(requests_to_cancel.c.request_id)
                )
            )
            .values(status = 'CANCELLED')
            .returning(
                self._table.c.request_id
            )
        )

        with write_transaction(self._get_engine(writer = True)) as conn:
            conn.execute(run_cancel_statement)

            # Consume the result while the connection is open
            cancelled = list(conn.execute(request_cancel_statement).scalars())

        return cancelled
