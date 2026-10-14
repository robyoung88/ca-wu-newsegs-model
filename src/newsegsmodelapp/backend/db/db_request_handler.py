import json
from typing import Callable, Sequence, overload, override

import sqlalchemy as sa

from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db import write_transaction, write_with_retries
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

    @override
    def add_request(
        self, 
        procedure_name: str, 
        active_project_id: str, 
        project_provider: NewsegsProjectProviderInterface, 
        procedure_class: str | None = None, 
        config: dict | None = None, 
        triggering_request: RunRequest | None = None
    ) -> int | None:

        get_req = None
        if not procedure_class:
            # Try and find procedure name in all registers
            for proc_class, reg in _REQUEST_REGISTERS.items():
                get_req = reg.get(procedure_name)
                if get_req is not None:
                    procedure_class = proc_class
                    break
                
            else:
                raise ValueError(f'Procedure name {procedure_name} not found.')
        else:
            reg = _REQUEST_REGISTERS[procedure_class]
            get_req = reg.get(procedure_name)
            if get_req is None:
                raise ValueError(f'Procedure name {procedure_name} not found in {procedure_class} request register. Available keys are {reg.keys()}.')

        match procedure_class:
            case 'run':
                request = get_req(active_project_id, project_provider, config)
            case 'postprocess':
                if triggering_request is None:
                    triggering_request = registers.RUN_REQUEST_REGISTER['_dummyrequest'](
                        active_project_id, project_provider, config
                    )
                request = get_req(triggering_request, config)
            case 'tabledraw':
                if triggering_request is None:
                    triggering_request = registers.RUN_REQUEST_REGISTER['_dummyrequest'](
                        active_project_id, project_provider, config
                    )
                request = get_req(triggering_request, config)
            case _:
                raise ValueError(f'Procedure class not recognised: {procedure_class}')

        stmt = (
            self._table.insert()
            .values({
                'request_class': procedure_class,
                'request_type': procedure_name,
                'project_id': active_project_id,
                'payload': json.dumps(request.as_dict())
            })
        )
        with write_transaction(self._get_engine()) as conn:
            res = conn.execute(stmt)
            if res and res.inserted_primary_key:
                return res.inserted_primary_key[0]

    def _row_to_runrequest(self, row) -> registers.RunRequest:
        constr = _REQUEST_CLASSES.get(row.request_class)
        if constr is None:
            constr = registers.RunRequest
        inst = constr.from_dict(json.loads(row.payload))
        # Set the request id and run id from the db
        inst.request_id = row.request_id
        if row.run_id:
            inst.run_id = row.run_id
        return inst

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
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall()
            requests = [self._row_to_runrequest(x) for x in rows]
        if singular:
            if not requests:
                raise ValueError(f'Request ID not found: {request_id[0]}')
            return requests[0]
        return requests

    @override
    def get_new_requests(self, active_project_id: str|None = None) -> list[registers.RunRequest]:
        
        stmt = (
            self._table.select()
            .where(sa.and_(
                self._table.c.dispatched == False,
                self._table.c.completed == False
                )
            )
        )
        if active_project_id:
            stmt = stmt.where(
                self._table.c.project_id == active_project_id
            )

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall()
            return [self._row_to_runrequest(x) for x in rows]

    @override
    def mark_dispatched(self, request_id: int | Sequence[int], run_id: int | None | Sequence[int | None]):
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

        data = [
            {'_id': id_, 'run_id_': r_id_, 'dis_': dis_}
            for id_, r_id_, dis_ in zip(request_id, run_id, are_dispatched)
        ]

        stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id == sa.bindparam("_id"))
            .values(
                dispatched = sa.bindparam('dis_'),
                run_id = sa.bindparam('run_id_'),
            )
        )

        write_with_retries(self._get_engine(), stmt, data)

    @override
    def mark_completed(self, request_id: int | Sequence[int], completed: bool = True):
        if isinstance(request_id, int):
            request_id = [request_id,]

        stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id.in_(request_id))
            .values(completed = completed)
        )
        write_with_retries(self._get_engine(), stmt)

    @override
    def increment_failure(self, request_id: int) -> bool:
        incr_stmt = (
            sa.update(self._table)
            .where(self._table.c.request_id == request_id)
            .values(
                run_id = None,
                retry_number = self._table.c.retry_number + 1
            )
            .returning(self._table.c.retry_number < self._table.c.max_retries)
        )

        with write_transaction(self._get_engine()) as conn:
            res = conn.execute(incr_stmt)
            if res:
                ok_retry = res.scalar()
                if ok_retry is not None:
                    return ok_retry
                else:
                    return False

        return False        
