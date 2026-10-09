import copy
import json
from typing import Any, Callable, Sequence, cast, overload, override

from cachetools import LRUCache
import numpy as np
import sqlalchemy as sa
from useful_types import SequenceNotStr

from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable, LightweightVariable
from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid
from newsegsmodelframework.newsegsvariable.variableprovider import VariableManagerInterface

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.util import jsonfuncs

_VARIABLE_MODEL_SECTION_MAP = {
    'model' : {
        'mod_gen': 'generation',
        'mod_cs._storage_params': 'cs',
        'mod_cs': 'cs',
        'mod_cs._spaceheat_params': 'cs',
        'mod_cs._dhw_params': 'cs',
        'mod_cs._appliance_params': 'cs',
        'mod_cs._ev_params': 'cs',
        '': 'modeldata',
    },
    'finance' : {
        '_unit_costs': 'financedata',
        '': 'financedata'
    }
}

def variable_to_raw_table_data(
    variable: Variable
) -> dict:
    model_sec = (
        _VARIABLE_MODEL_SECTION_MAP
        .get(variable.configuration_type, {})
        .get(variable.model_section, '')  # type: ignore
    )

    pars = variable.raw_parameters
    p0 = pars[0] if len(pars) > 0 else None
    p1 = pars[1] if len(pars) > 1 else None

    varid = variable_uid(variable)

    odict = dict(
        id = variable.id,
        varid = varid,
        interface_section = variable.interface_section,
        interface_key = variable.interface_key,
        interface_subindex = variable.interface_subindex,
        revision = variable.revision,
        component_type = model_sec,
        variable_type = variable.variable_type,
        distribution = variable.distribution.distribution,
        parameterisation_index = variable.parameterisation_index,

        raw_parameter_0 = json.dumps(p0, cls = jsonfuncs.NumpyEncoder) if p0 is not None else None,
        raw_parameter_1 = json.dumps(p1, cls = jsonfuncs.NumpyEncoder) if p1 is not None else None,
        last_deterministic_value = json.dumps(variable.deterministic_value, cls = jsonfuncs.NumpyEncoder),

        dsa_show = variable.dsa_show,
        dsa_selectable = variable.dsa_selectable,
        dsa_selected = variable.dsa_selected,
        dsa_bounds_type = variable.dsa_bounds_type,
        dsa_lower = json.dumps(variable.dsa_lower, cls = jsonfuncs.NumpyEncoder) if variable.dsa_lower is not None else None,
        dsa_upper = json.dumps(variable.dsa_upper, cls = jsonfuncs.NumpyEncoder) if variable.dsa_upper is not None else None,

        psa_show = variable.psa_show,
        psa_selectable = variable.psa_selectable,
        psa_selected = variable.psa_selected,

        optim_show = variable.optim_show,
        optim_selectable = variable.optim_selectable,
        optim_selected = variable.optim_selected,
        optim_min = json.dumps(variable.optim_min, cls = jsonfuncs.NumpyEncoder) if variable.optim_min is not None else None,
        optim_max = json.dumps(variable.optim_max, cls = jsonfuncs.NumpyEncoder) if variable.optim_max is not None else None,

        payload = variable.json_dumps(),

        label = variable.name,
        icon_name = json.dumps(variable.icon_name),
        unit = variable.unit,

        interface_min = variable.interface_min,
        interface_max = variable.interface_max,
        interface_step = variable.interface_step,
        formatter_dp = variable.formatter_dp if hasattr(variable, 'formatter_dp') else None,
    )

    return odict

_json_attributes = (
    'raw_parameter_0',
    'raw_parameter_1',
    'last_deterministic_value',
    'dsa_lower',
    'dsa_upper',
    'optim_min',
    'optim_max',
    'icon_name',
)

def _variable_from_json(json_str) -> Variable:
    constr_dict = json.loads(json_str)
    return cast(
        Variable,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )

def _variable_from_dict(constr_dict: dict) -> Variable:
    return cast(
        Variable,
        find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
    )

class FromDatabaseVariableProvider(VariableManagerInterface):
    _table = tbls.variable_configs

    _lightweight_variable_columns = tuple(
        tbls.variable_configs.columns[x] for x in (
            'id',
            'varid',
            'interface_section',
            'interface_key',
            'interface_subindex',

            'variable_type',
            'distribution',

            'label',
            'icon_name',
            'unit',

            'interface_min',
            'interface_max',
            'interface_step',
            'formatter_dp',

            'distribution',
            'last_deterministic_value',
            'raw_parameter_0',
            'raw_parameter_1',
            'revision'
        )
    )

    _full_lightweight_variable_columns = _lightweight_variable_columns + tuple(
        tbls.variable_configs.columns[x] for x in (
            'parameterisation_index',

            'dsa_show',
            'dsa_selectable',
            'dsa_selected',
            'dsa_lower',
            'dsa_upper',

            'psa_show',
            'psa_selectable',
            'psa_selected',

            'optim_show',
            'optim_selectable',
            'optim_selected',
            'optim_min',
            'optim_max',
        )
    )

    def __init__(self, get_engine: Callable[[], sa.Engine]):
        self._get_engine = get_engine

    @classmethod
    def _reconstruct_variable(cls, row) -> Variable:
        metadata = dict(row._mapping)
        payload = metadata.pop('payload')
        revision = metadata.pop('revision')
        p0 = metadata.pop('raw_parameter_0')
        p1 = metadata.pop('raw_parameter_1')
        constr_dict = json.loads(payload)
        # Update the dictionary before construction where possible
        update_dict = {
            k: json.loads(metadata[k]) if k in _json_attributes else metadata[k] 
            for k in metadata.keys() if k in constr_dict
        }

        for k in update_dict.keys():
            del metadata[k]

        constr_dict.update(update_dict)
        v = _variable_from_dict(constr_dict)
        for k, dictval in metadata.items():
            if k in _json_attributes and dictval is not None:
                dictval = json.loads(dictval)
            try:
                curval = getattr(v, k)
            except AttributeError:
                continue
            if curval != dictval:
                try:
                    setattr(v, k, dictval)
                except AttributeError:
                    # Here if trying to set a read-only
                    continue

        raw_pars = v.raw_parameters
        cp0 = json.dumps(raw_pars[0], cls = jsonfuncs.NumpyEncoder) if len(raw_pars) > 0 else None
        cp1 = json.dumps(raw_pars[1], cls = jsonfuncs.NumpyEncoder) if len(raw_pars) > 1 else None
        if p0 is not None and p0 != cp0:
            par0_new = json.loads(p0)
            if isinstance(raw_pars[1], np.ndarray):
                par0_new = np.array(par0_new)
            if p1 is not None and p1 != cp1:
                par1_new = json.loads(p1)
                if isinstance(raw_pars[1], np.ndarray):
                    if len(raw_pars[1].shape) == 2:
                        par1_new = np.array(par1_new).reshape((len(par0_new), -1))
                    else:
                        par1_new = np.array(par1_new)
                if len(raw_pars) < 3:
                    v.set_parameters((par0_new, par1_new))
                else:
                    newpars = (par0_new, par1_new, *raw_pars[2:])
                    v.set_parameters(newpars)
            else:
                rp0 = raw_pars[0]
                if len(rp0) == len(par0_new):
                    for idx, val in par0_new:
                        if val != rp0[idx]:
                            v.set_single_parameter(val, 0, idx)
                else:
                    if len(raw_pars) > 1:
                       v.set_parameters((par0_new, *raw_pars[1:]))
                    else:
                        v.set_parameters((par0_new, ))
        elif p1 is not None and p1 != cp1:
            par1_new = json.loads(p0)
            if isinstance(raw_pars[1], np.ndarray):
                if len(raw_pars[1].shape) == 2:
                    par1_new = np.array(par1_new).reshape(raw_pars.shape)
                else:
                    par1_new = np.array(par1_new)
            if len(raw_pars) < 3:
                v.set_parameters((raw_pars[0], par1_new))
            else:
                newpars = (raw_pars[0], par1_new, *raw_pars[2:])
                v.set_parameters(newpars)

        v.soft_dirty = False
        v.revision = revision
        # v.syncronise()

        return v

    @classmethod
    def _reconstruct_lightweight_variable(cls, row) -> LightweightVariable:
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        v = LightweightVariable.from_dict(metadata)
        v.raw_parameter_0 = json.loads(v.raw_parameter_0) if v.raw_parameter_0 is not None else None
        v.raw_parameter_1 = json.loads(v.raw_parameter_1) if v.raw_parameter_1 is not None else None
        v.revision = revision
        v._syncronise()
        return v

    @classmethod
    def _reconstruct_full_lightweight_variable(cls, row) -> FullLightweightVariable:
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        v = FullLightweightVariable.from_dict(metadata)
        v.raw_parameter_0 = json.loads(v.raw_parameter_0) if v.raw_parameter_0 is not None else None
        v.raw_parameter_1 = json.loads(v.raw_parameter_1) if v.raw_parameter_1 is not None else None
        v.dsa_lower = json.loads(v.dsa_lower) if v.dsa_lower is not None else None
        v.dsa_upper = json.loads(v.dsa_upper) if v.dsa_upper is not None else None
        v.optim_min = json.loads(v.optim_min) if v.optim_min is not None else None
        v.optim_max = json.loads(v.optim_max) if v.optim_max is not None else None
        v.revision = revision
        v._syncronise()
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
                self._table.select()
                .where(self._table.c.id == instance_id)
            )
        else:
            is_sequence = True
            stmt = (
                self._table.select()
                .where(self._table.c.id.in_(instance_id))
            )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall() # Fetch to avoid leaving the connection open
        
        reconstructed_vars = [self._reconstruct_variable(row) for row in rows]
        if not is_sequence:
            return reconstructed_vars[0]
        
        varmap = {x.id:x for x in reconstructed_vars}
        return [varmap[x] for x in instance_id]

    def get_lightweight_variable(
        self, 
        instance_id: str | SequenceNotStr[str]
    ) -> LightweightVariable | SequenceNotStr[LightweightVariable]:
        is_sequence = False
        if isinstance(instance_id, str):
            stmt = (
                sa.select(*self._lightweight_variable_columns)
                .where(self._table.c.id == instance_id)
            )
        else:
            is_sequence = True
            stmt = (
                sa.select(
                    *self._lightweight_variable_columns
                )
                .where(self._table.c.id.in_(instance_id))
            )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall() # Fetch to avoid leaving the connection open
        
        reconstructed_vars = [self._reconstruct_lightweight_variable(row) for row in rows]
        if not is_sequence:
            return reconstructed_vars[0]

        varmap = {x.id:x for x in reconstructed_vars}
        return [varmap[x] for x in instance_id]

    def get_full_lightweight_variable(
        self, 
        instance_id: str | SequenceNotStr[str]
    ) -> FullLightweightVariable | SequenceNotStr[FullLightweightVariable]:
        is_sequence = False
        if isinstance(instance_id, str):
            stmt = (
                sa.select(*self._full_lightweight_variable_columns)
                .where(self._table.c.id == instance_id)
            )
        else:
            is_sequence = True
            stmt = (
                sa.select(*self._full_lightweight_variable_columns)
                .where(self._table.c.id.in_(instance_id))
            )
        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall() # Fetch to avoid leaving the connection open
        
        reconstructed_vars = [self._reconstruct_full_lightweight_variable(row) for row in rows]
        if not is_sequence:
            return reconstructed_vars[0]

        varmap = {x.id:x for x in reconstructed_vars}
        return [varmap[x] for x in instance_id]

    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        stmt = (
            self._table.select()
            .where(self._table.c.varid == variable_id)
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
                rev_stmt = sa.update(self._table).where(self._table.c.id == sa.bindparam('b_id'))
                conn.execute(rev_stmt, rev_payload)

            if update_payload:
                # Cannot use 'id' as the bindparam - rename it.
                update_payload = [{'b_id': x.pop('id'), **x} for x in update_payload]
                update_stmt = sa.update(self._table).where(self._table.c.id == sa.bindparam('b_id'))
                conn.execute(update_stmt, update_payload)

            if insert_payload:
                insert_stmt = self._table.insert()
                conn.execute(insert_stmt, insert_payload)

    @override
    def delete_variable(self, variable_id: str | SequenceNotStr[str]) -> list[str]:
        if isinstance(variable_id, str):
            variable_id = [variable_id]
        del_stmt = (
            self._table.delete()
            .where(self._table.c.id.in_(variable_id))
        )
        with self._get_engine().begin() as conn:
            result = conn.execute(del_stmt)
            return [str(result.rowcount)]

    @overload
    def get_variable_metadata(
        self,
        instance_id: str,
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any]:
        ...

    @overload 
    def get_variable_metadata(
        self,
        instance_id: SequenceNotStr[str],
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, dict[str, Any]]:
        ...

    def get_variable_metadata(
        self,
        instance_id: str | SequenceNotStr[str],
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        is_single_id = isinstance(instance_id, (str, bytes))
        instance_id = [instance_id] if is_single_id else list(instance_id)

        cols = [metadata_ids] if isinstance(metadata_ids, (str, bytes)) else list(metadata_ids)

        if not instance_id:
            return {}

        pk_col = list(self._table.primary_key.columns)[0]
        select_cols = [self._table.c[col_name] for col_name in cols]

        fetch_cols = list({pk_col, *select_cols})
        stmt = sa.select(*fetch_cols).where(pk_col.in_(instance_id))
        with self._get_engine().connect() as conn:
            results = conn.execute(stmt).mappings().all()

        mapped_data = {
            row[pk_col.name]: {c: row[c] for c in cols} for row in results
        }

        if is_single_id:
            return mapped_data.get(instance_id[0], {})

        return mapped_data

    def set_variable_metadata(
        self, 
        instance_id: str, 
        metadata_id: str, 
        metadata_value: Any
    ):
        
        pk_col = list(self._table.primary_key.columns)[0]
        update_col = self._table.c[metadata_id]

        changed = sa.or_(
            update_col.is_distinct_from(metadata_value)
        )

        stmt = (
            sa.update(self._table)
            .where(pk_col == instance_id)
            .values(
                revision= sa.case(
                    (changed, self._table.c.revision + 1),
                    else_ = self._table.c.revision
                )
                **{update_col.name: metadata_value})
        )

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        return

    # def set_variable_parameter(
    #     self,
    #     instance_id: str,
    #     parameter_value: Any,
    #     parameter_index: int,
    # ):
        

class CachedFromDatabaseVariableProvider(
    FromDatabaseVariableProvider
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._variable_cache = LRUCache(maxsize = 100)
        self._lightweight_variable_cache = LRUCache(maxsize = 100)
        self._full_lightweight_variable_cache = LRUCache(maxsize = 100)

    @override
    def get_variable(self, instance_id):
        if isinstance(instance_id, str):
            is_sequence = False
            instance_id = [instance_id]
        else:
            is_sequence = True

        revisions = self.get_variable_metadata(instance_id, 'revision')
        rlist = []
        get_list = []
        for idx, id_ in enumerate(instance_id):
            found_var = False
            if id_ in self._variable_cache:
                vx = self._variable_cache[id_]
                if vx.revision == revisions[idx]:
                    rlist.append(vx)
                    found_var = True
            if not found_var:
                rlist.append(None)
                get_list.append(id_)

        if len(get_list) > 0:
            vars_from_db = super().get_variable(get_list)
            jdx = 0
            for idx, id_ in enumerate(rlist):
                if id_ is None:
                    vx = vars_from_db[jdx]
                    rlist[idx] = vx
                    self._variable_cache[vx.id]
                    jdx += 1

        if is_sequence:
            return rlist
        return rlist[0]

    @override
    def get_lightweight_variable(self, instance_id):
        if isinstance(instance_id, str):
            is_sequence = False
            instance_id = [instance_id]
        else:
            is_sequence = True

        revisions = self.get_variable_metadata(instance_id, 'revision')
        rlist = []
        get_list = []
        for id_ in instance_id:
            found_var = False
            if id_ in self._lightweight_variable_cache:
                vx = self._lightweight_variable_cache[id_]
                if vx.revision == revisions[id_]['revision']:
                    rlist.append(vx)
                    found_var = True
            if not found_var:
                rlist.append(None)
                get_list.append(id_)

        if len(get_list) > 0:
            vars_from_db = super().get_lightweight_variable(get_list)
            jdx = 0
            for idx, id_ in enumerate(rlist):
                if id_ is None:
                    vx = vars_from_db[jdx]
                    rlist[idx] = vx
                    self._lightweight_variable_cache[vx.id] = vx
                    jdx += 1

        if is_sequence:
            return rlist
        return rlist[0]

    @override
    def get_full_lightweight_variable(self, instance_id):
        if isinstance(instance_id, str):
            is_sequence = False
            instance_id = [instance_id]
        else:
            is_sequence = True

        revisions = self.get_variable_metadata(instance_id, 'revision')
        rlist = []
        get_list = []
        for id_ in instance_id:
            found_var = False
            if id_ in self._full_lightweight_variable_cache:
                vx = self._full_lightweight_variable_cache[id_]
                if vx.revision == revisions[id_]['revision']:
                    rlist.append(vx)
                    found_var = True
            if not found_var:
                rlist.append(None)
                get_list.append(id_)

        if len(get_list) > 0:
            vars_from_db = super().get_full_lightweight_variable(get_list)
            jdx = 0
            for idx, id_ in enumerate(rlist):
                if id_ is None:
                    vx = vars_from_db[jdx]
                    rlist[idx] = vx
                    self._full_lightweight_variable_cache[vx.id] = vx
                    jdx += 1

        if is_sequence:
            return rlist
        return rlist[0]
    