import copy
import json
from typing import Callable, Sequence, cast, overload, override

import sqlalchemy as sa
from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db.project import variable_to_raw_table_data
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsvariable.variable import Variable
from newsegsmodelframework.newsegsvariable.variableprovider import VariableManagerInterface

from newsegsmodelapp.backend.db import tables as tbls

def _variable_from_json(json_str) -> Variable:
    constr_dict = json.loads(json_str)
    return cast(
        Variable,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )
    

class FromDatabaseVariableProvider(VariableManagerInterface):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        self._get_engine = get_engine

    def _reconstruct_variable(self, row) -> Variable:
        v = _variable_from_json(row.payload)
        v.id = row.id # ID may have been reassigned in database
        v.soft_dirty = False
        if v.revision != row.revision:
            if v.revision > row.revision:
                print(f'WARNING - Variable has been constructed with revision greater than stored in row: Payload = {v.revision}, Row = {row.revision}')
            print(f'Syncronising Variable revision ({v.id}): {v.revision} -> {row.revision}')
            v.revision = row.revision
            v._config._last_syncronised = v.revision
        
        if v.modified:
            raise ValueError(f'Variable has been reconstructed in modified form - Item revision = {v.revision}, last synced = {v._config._last_syncronised}')
        return v
    
    @overload
    def get_variable(self, instance_id: str) -> Variable:
        ...

    @overload
    def get_variable(self, instance_id: SequenceNotStr[str]) -> SequenceNotStr[Variable]:
        ...
    
    def get_variable(self, instance_id: str | SequenceNotStr[str]) -> Variable | SequenceNotStr[Variable]:
        is_sequence = False
        if isinstance(instance_id, str):
            stmt = (
                tbls.variable_configs.select()
                .where(tbls.variable_configs.c.id == instance_id)
            )
        else:
            is_sequence = True
            stmt = (
                tbls.variable_configs.select()
                .where(tbls.variable_configs.c.id.in_(instance_id))
            )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt)
            reconstructed_vars = [self._reconstruct_variable(row) for row in rows]
        if not is_sequence:
            return reconstructed_vars[0]
        
        varmap = {x.id:x for x in reconstructed_vars}
        return [varmap[x] for x in instance_id]

    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        stmt = (
            tbls.variable_configs.select()
            .where(tbls.variable_configs.c.varid == variable_id)
        )

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall()

        if not rows:
            raise KeyError(f'Variable type {variable_id} not found - a first application of this variable must be added.')

        row = rows[index]
        return _variable_from_json(row.payload)

    def duplicate_variable(self, instance_id: str) -> Variable:
        v1 = self.get_variable(instance_id)
        v2 = cast(Variable, copy.deepcopy(v1))
        v2.id = v2.generate_new_id()
        vardata = variable_to_raw_table_data(v2)
        stmt = (tbls.variable_configs.insert().values(vardata))
        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        return v2

    def add_variable(self, var: Variable) -> str:
        vardata = variable_to_raw_table_data(var)
        stmt = (tbls.variable_configs.insert().values(vardata))
        with self._get_engine().begin() as conn:
            res = conn.execute(stmt)

        if res is None:
            raise ValueError(f'Value could not be inserted: {var}')

        return res.inserted_primary_key[0] # pyright: ignore[reportOptionalSubscript]

    def get_varids(self) -> tuple[str, ...]:
        stmt = sa.select(tbls.variable_configs.c.varid).distinct()
        with self._get_engine().connect() as conn:
            varids = conn.scalars(stmt)
        return tuple(varids)

    @override
    def upsert_variable(self, var: Variable | Sequence[Variable], force: bool = False):
        """Insert or update a variable or list of variables into the database.
        
        Args:
            var: A variable or sequence of variables to synchronise.
            force: Overwrite the variable(s) regardless of whether their revision number has incremented.
        """
        if isinstance(var, Variable):
            var = [var, ]

        current_revisions = {x.id: x.revision for x in var}
        soft_dirty = {x.id: x.soft_dirty for x in var}
        uids = list(current_revisions.keys())

        # Get saved revision if exists
        stmt = (
                sa.select(
                    tbls.variable_configs.c.id,
                    tbls.variable_configs.c.revision
                )
                .where(tbls.variable_configs.c.id.in_(uids))
            )
        engine = self._get_engine()
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        saved_revisions = {x.id: x.revision for x in rows}
        existing_uids = set({str(x) for x in saved_revisions.keys()})
        new_inserts = [str(x) for x in uids if x not in existing_uids]
        requires_revision_increment = []
        if not force:
            requires_update = [x for x in existing_uids if (current_revisions[x] != saved_revisions[x]) or soft_dirty[x]]
            for x in var:
                if x.id not in new_inserts and x.id not in requires_update:
                    if x.chain_modified:
                        requires_revision_increment.append(x.id)
                        x.revision += 1
        else:
            requires_update = existing_uids

        requires_data = set(requires_update)
        requires_data.update(set(new_inserts))

        requires_sync = copy.copy(requires_data)
        requires_sync.update(set(requires_revision_increment))

        # First, do the updates, then do the inserts
        for v in var:
            if v.id in requires_sync:
                # TODO: Consider whether to set a rollback here in case we can't access the DB
                v.syncronise()

        vardata = {v.id: variable_to_raw_table_data(v) for v in var if v.id in requires_data}
        revdata = {v.id: {'id': v.id, 'revision': v.revision} for v in var if v.id in requires_revision_increment}

        update_payload = [vardata[x] for x in requires_update]
        insert_payload = [vardata[x] for x in new_inserts]
        rev_payload = [revdata[x] for x in requires_revision_increment]

        if not (update_payload or insert_payload):
            return
        
        with engine.begin() as conn:
            if rev_payload:
                # Cannot use 'id' as the bindparam - rename it
                rev_payload = [{'b_id': x.pop('id'), **x} for x in rev_payload]
                rev_stmt = sa.update(tbls.variable_configs).where(tbls.variable_configs.c.id == sa.bindparam('b_id'))
                conn.execute(rev_stmt, rev_payload)

            if update_payload:
                # Cannot use 'id' as the bindparam - rename it.
                update_payload = [{'b_id': x.pop('id'), **x} for x in update_payload]
                update_stmt = sa.update(tbls.variable_configs).where(tbls.variable_configs.c.id == sa.bindparam('b_id'))
                conn.execute(update_stmt, update_payload)

            if insert_payload:
                insert_stmt = tbls.variable_configs.insert()
                conn.execute(insert_stmt, insert_payload)

    @override
    def delete_variable(self, variable_id: str | SequenceNotStr[str]) -> list[str]:
        if isinstance(variable_id, str):
            variable_id = [variable_id]
        del_stmt = (
            tbls.variable_configs.delete()
            .where(tbls.variable_configs.c.id.in_(variable_id))
        )
        with self._get_engine().begin() as conn:
            result = conn.execute(del_stmt)
            return [str(result.rowcount)]
    