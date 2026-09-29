import copy
import json
from typing import Any, Callable, Literal, Optional, Sequence, cast, overload, override

from cachetools import LRUCache
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.exc import NoResultFound
from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db import DependentObjectsExistError, db_snapshot
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, NewsegsComponentManagerInterface, NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface

from newsegsmodelapp.backend.db.project import component_to_raw_table_data, finance_model_to_raw_table_data, metamodel_to_raw_table_data, project_to_raw_table_data
from newsegsmodelapp.backend.db.project import energy_model_to_raw_table_data
from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import ON_MISSING_OPTION, NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsvariable.variable import Variable

class FromDatabaseNewsegsComponentProvider(
    NewsegsComponentManagerInterface
):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        self._get_engine = get_engine
        self._table = tbls.component_configs

    def _component_from_json(self, json_payload: str) -> NewsegsComponent:
        constr_dict = json.loads(json_payload)
        return cast(
            NewsegsComponent,
            find_constructor(constr_dict['constructor_class'], constr_dict['class'])(constr_dict)
        )

    def _assign_updated_child_uids(self, obj, row):
        """Given the row for the component, get the live ids for each of the child components.
        
        Also take the opportunity to update any metadata that may have changed."""
        obj.name = row._mapping['label']
        return obj

    def _reattach_children(self, obj):
        """Once the component has updated uids for retrieving children, get them using the necessary providers."""
        return obj

    def _reconstruct_component(self, json_payload, row) -> NewsegsComponent:
        obj = self._component_from_json(json_payload)
        obj.id = row.id # The ID may have changed from the payload - set it now
        obj = self._assign_updated_child_uids(obj, row)
        obj = self._reattach_children(obj)
        if obj.revision != row.revision:
            if obj.revision > row.revision:
                print(f'WARNING - Component has been constructed with revision greater than stored in row: Payload = {obj.revision}, Row = {row.revision}')
            print(f'Syncronising Component revision ({obj.id}): {obj.revision} -> {row.revision}')
            obj.revision = row.revision
            obj._config._last_syncronised = obj.revision
        if obj.chain_modified:
            raise ValueError('Component has been reconstructed with modified children.')
        return obj

    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if component.modified:
            raise ValueError(f'{component.id} is being upserted in a modified state')
        return component_to_raw_table_data(component)

    @overload
    def get_component(self, component_id: str) -> NewsegsComponent:
        ...

    @overload
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsComponent]:
        ...

    @override
    def get_component(self, component_id: str | SequenceNotStr[str]) -> NewsegsComponent | SequenceNotStr[NewsegsComponent]:
        is_sequence = False
        if isinstance(component_id, str):
            stmt = (
                self._table.select()
                .where(self._table.c.id == component_id)
            )
        else:
            is_sequence = True
            stmt = (
                self._table.select()
                .where(self._table.c.id.in_(component_id))
            )

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall()

        reconstructed_components = [self._reconstruct_component(row.payload, row) for row in rows]
        if not is_sequence:
            if len(reconstructed_components) == 0:
                raise ValueError(f'Component not found: {component_id} in table {self._table}')
            return reconstructed_components[0]

        compmap = {x.id: x for x in reconstructed_components}
        return [compmap[x] for x in component_id]

    def _create_duplicate_component(self, original: NewsegsComponent) -> NewsegsComponent:
        comp1 = original
        comp2 = copy.deepcopy(comp1)
        comp2.id = comp2.generate_new_id()
        for childattr in comp2.get_component_attributes():
            setattr(
                comp2,
                childattr,
                self.duplicate_component(getattr(comp2, childattr))
            )
        return comp2
    
    @override
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsComponent:
        if isinstance(component_id, str):
            orig = self.get_component(component_id)
        else:
            orig = component_id
        comp2 = self._create_duplicate_component(orig)
        comp2.revision = orig.revision
        self.upsert_component(comp2, force = False)
        
        return comp2

    @override
    def add_component(self, component: NewsegsComponent) -> str:
        self.upsert_component(component, force = True)
        return component.id
        
    @override
    def get_default_component(
        self,
        component_type: str,
        index: int = -1
    ) -> NewsegsComponent:
        stmt = (
            self._table.select()
            .where(self._table.c.component_type == component_type)
        )

        with self._get_engine().connect() as conn:
            rows = conn.execute(stmt).fetchall()

        if not rows:
            raise KeyError(f'Component type {component_type} not found - a first application of this component must be added via add_component.')

        row = rows[index]
        return self._reconstruct_component(row.payload, row)

    @override
    def upsert_component(
        self, 
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent], 
        force: bool = False,
        tbl: Optional[sa.Table] = None
    ) -> None:
        if tbl is None:
            tbl = self._table
        if isinstance(component, NewsegsComponent):
            component = [component, ]

        current_revisions = {x.id: x.revision for x in component}
        uids = list(current_revisions.keys())

        # Get saved revision if exists
        stmt = (
            sa.select(
                tbl.c.id,
                tbl.c.revision
            )
            .where(tbl.c.id.in_(uids))
        )
        engine = self._get_engine()
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        saved_revisions = {x.id: x.revision for x in rows}
        existing_uids = set(saved_revisions.keys())
        new_inserts = [x for x in uids if x not in existing_uids]
        if not force:
            requires_update = [x for x in existing_uids if current_revisions[x] != saved_revisions[x]]
            # If the object exists and has a matching version number but its children have been modified
            # then we do a simple bump of the revision number to indicate that downstream results are stale
            requires_revision_increment = []
            for comp in component:
                if comp.id not in new_inserts and comp.id not in requires_update:
                    if comp.chain_modified:
                        requires_revision_increment.append(comp.id)
                        comp.revision += 1
                        # Update the table config revision if components have been modified.
                        if hasattr(comp, 'table_config'):
                            if not comp.table_config.modified:
                                comp.table_config.revision += 1
        else:
            requires_update = existing_uids
            requires_revision_increment = []

        requires_data = set(requires_update)
        requires_data.update(set(new_inserts))

        requires_sync = copy.copy(requires_data)
        requires_sync.update(set(requires_revision_increment))

        # First, do the updates, then do the inserts
        for cmp in component:
            if cmp.id in requires_sync:
                # TODO: Consider whether to set a rollback here in case we can't access DB
                
                #### Save out all child components ####
                children = cmp.get_components()
                if children:
                    self.upsert_component(children)

                cmp.syncronise()

        cmpdata = {cmp.id: self._component_to_table_data(cmp) for cmp in component if cmp.id in requires_data}

        revdata = {cmp.id: {'id': cmp.id, 'revision': cmp.revision,} for cmp in component if cmp.id in requires_revision_increment}

        update_payload = [cmpdata[x] for x in requires_update]
        insert_payload = [cmpdata[x] for x in new_inserts]
        rev_payload = [revdata[x] for x in requires_revision_increment]

        if not (update_payload or insert_payload):
            return
        
        with engine.begin() as conn:
            if rev_payload:
                # Cannot use 'id' as the bindparam - rename it
                rev_payload = [{'b_id': x.pop('id'), **x} for x in rev_payload]
                rev_stmt = sa.update(tbl).where(tbl.c.id == sa.bindparam('b_id'))
                conn.execute(rev_stmt, rev_payload)

            if update_payload:
                # Cannot use 'id' as the bindparam - rename it
                update_payload = [{'b_id': x.pop('id'), **x} for x in update_payload]
                update_stmt = sa.update(tbl).where(tbl.c.id == sa.bindparam('b_id'))
                conn.execute(update_stmt, update_payload)

            if insert_payload:
                insert_stmt = tbl.insert()
                conn.execute(insert_stmt, insert_payload)

    def _delete_one_component(
            self, 
            component_id: str,
            ignore_ids: list[str] = []
            ) -> None:
        # Assume that we are dealing only with members of the component_config table.

        # Any energy model configurations using this component must be identified
        get_em_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.em_configs)
            .where(
                sa.and_(
                    tbls.em_configs.c.id.not_in(ignore_ids),
                    (
                        (tbls.em_configs.c.grid_config_id == component_id) |
                        (tbls.em_configs.c.generation_config_id == component_id) |
                        (tbls.em_configs.c.cs_config_id == component_id) |
                        (tbls.em_configs.c.modeldata_config_id == component_id) |
                        (tbls.em_configs.c.table_config_id == component_id)
                    )
                )
            )
        )

        # Any finance model configurations using this component must be identified
        get_fm_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.fm_configs)
            .where(
                sa.and_(
                    tbls.fm_configs.c.id.not_in(ignore_ids),
                    (
                        (tbls.fm_configs.c.financedata_config_id == component_id) |
                        (tbls.fm_configs.c.table_config_id == component_id)
                    )
                )
            )
        )

        # Any metamodels using this component directly must be identified
        get_mm_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.metamodels)
            .where(
                sa.and_(
                    tbls.metamodels.c.id.not_in(ignore_ids),
                    (
                        (tbls.metamodels.c.table_config_id == component_id)
                    )
                )
            )
        )

        # Any projects using this component directly must be identified
        get_proj_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.projects)
            .where(
                sa.and_(
                    tbls.projects.c.id.not_in(ignore_ids),
                    (
                        (tbls.projects.c.dsa_component_config_id == component_id) |
                        (tbls.projects.c.psa_component_config_id == component_id) |
                        (tbls.projects.c.table_config_id == component_id)
                    )
                )
            )
        )

        # All associated results must be deleted
        del_res_stmt = (
            tbls.results.delete()
            .where(tbls.results.c.component_config_id == component_id)
        )

        # And then the component will be free to delete
        del_comp_stmt = (
            tbls.component_configs.delete()
            .where(tbls.component_configs.c.id == component_id)
        )

        with self._get_engine().connect() as conn:
            for trial_stmt in (
                get_em_count_stmt,
                get_fm_count_stmt,
                get_mm_count_stmt,
                get_proj_count_stmt
            ):
                count = conn.execute(trial_stmt).scalar()
                if count:
                    raise DependentObjectsExistError(f'Cannot delete - dependents exist for component {component_id}')

            # Proceed with deletion
            conn.execute(del_res_stmt)
            conn.execute(del_comp_stmt)
            conn.commit()

    @override
    def delete_component(
        self, 
        component_id: str | SequenceNotStr[str],
        ignore_ids: list[str] = []
    ) -> list[str]:

        if isinstance(component_id, str):
            component_id = [component_id, ]

        failures = []
        for id in component_id:
            try:
                self._delete_one_component(id)
            except DependentObjectsExistError:
                failures.append(id)

        return failures

    @overload
    def get_component_metadata(
        self,
        component_id: str,
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any]:
        ...

    @overload 
    def get_component_metadata(
        self,
        component_id: SequenceNotStr[str],
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, dict[str, Any]]:
        ...

    def get_component_metadata(
        self,
        component_id: str | SequenceNotStr[str],
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        is_single_id = isinstance(component_id, (str, bytes))
        component_id = [component_id] if is_single_id else list(component_id)

        cols = [metadata_ids] if isinstance(metadata_ids, (str, bytes)) else list(metadata_ids)

        if not component_id:
            return {}

        pk_col = list(self._table.primary_key.columns)[0]
        select_cols = [self._table.c[col_name] for col_name in cols]

        fetch_cols = list({pk_col, *select_cols})
        stmt = sa.select(*fetch_cols).where(pk_col.in_(component_id))
        with self._get_engine().connect() as conn:
            results = conn.execute(stmt).mappings().all()

        mapped_data = {
            row[pk_col.name]: {c: row[c] for c in cols} for row in results
        }

        if is_single_id:
            return mapped_data.get(component_id[0], {})

        return mapped_data

    @override
    def set_component_metadata(
        self, 
        component_id: str, 
        metadata_id: str, 
        metadata_value: Any
    ):
        
        pk_col = list(self._table.primary_key.columns)[0]
        update_col = self._table.c[metadata_id]

        stmt = (
            sa.update(self._table)
            .where(pk_col == component_id)
            .values(**{update_col.name: metadata_value})
        )

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        return

class FromDatabaseNewsegsEMProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.em_configs
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

    @override
    def _assign_updated_child_uids(self, obj, row):
        super()._assign_updated_child_uids(obj, row)
        if isinstance(obj, NewsegsModelInterface):
            obj._component_ids['grid'] = row.grid_config_id
            obj._component_ids['generation'] = row.generation_config_id
            obj._component_ids['consumption_storage'] = row.cs_config_id
            obj._component_ids['table_config'] = row.table_config_id
        return obj

    @override
    def _reattach_children(self, obj):
        r0 = obj.revision
        obj = super()._reattach_children(obj)
        obj.reattach_components(self._component_provider)
        if obj.revision != r0:
            raise ValueError('Model revision incremented during subcomponent attachment - from {r0} to {obj.revision}')
        return obj

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsModelInterface):
            return super()._component_to_table_data(component)
        if component.modified:
            raise ValueError(f'{component.id} is being upserted in a modified state')
        return energy_model_to_raw_table_data(component)
        
    @override
    def upsert_component(
        self,
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent], 
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        if isinstance(component, NewsegsModelInterface) or isinstance(component, Sequence) and all(isinstance(x, NewsegsModelInterface) for x in component):
            return super().upsert_component(component, force, tbl)
        else:
            return self._component_provider.upsert_component(component, force, tbl)

    @override
    def _delete_one_component(
        self, 
        component_id: str,
        ignore_ids: list[str] = [],
    ) -> None:
        # Assume that we are dealing only with members of the em_configs table

        # Any metamodel configurations using this model must be identified
        get_mm_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.metamodels)
            .where(
                sa.and_(
                    tbls.metamodels.c.id.not_in(ignore_ids),
                    (
                        (tbls.metamodels.c.em_config_id == component_id)
                    )
                )
            )
        )

        # Child components should be identified and subsequently deleted, where appropriate
        get_child_component_id_stmt = (
            sa.select(
                self._table.c.grid_config_id,
                self._table.c.generation_config_id,
                self._table.c.cs_config_id,
                self._table.c.modeldata_config_id,
                self._table.c.table_config_id,
            )
            .where(self._table.c.id == component_id)
        )

        del_stmt = (
            self._table.delete()
            .where(self._table.c.id == component_id)
        )

        child_ids = []
        with self._get_engine().connect() as conn:
            for trial_stmt in (
                get_mm_count_stmt,
            ):
                count = conn.execute(trial_stmt).scalar()
                if count:
                    raise DependentObjectsExistError(f'Cannot delete - dependents exist for energy model {component_id}')

            # Get child ids
            row = conn.execute(get_child_component_id_stmt).fetchone()
            if row:
                child_ids = [x for x in row if x]

            # Delete model
            conn.execute(del_stmt)
            conn.commit()

        # Delete children
        _ = self._component_provider.delete_component(child_ids)


class FromDatabaseNewsegsFMProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.fm_configs
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

    @override
    def _assign_updated_child_uids(self, obj, row):
        super()._assign_updated_child_uids(obj, row)
        if isinstance(obj, NewsegsFinanceInterface):
            obj._component_ids['finance_data'] = row.financedata_config_id
            obj._component_ids['table_config'] = row.table_config_id
        return obj
    
    @override
    def _reattach_children(self, obj):
        obj = super()._reattach_children(obj)
        obj.reattach_components(self._component_provider)
        return obj

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsFinanceInterface):
            return super()._component_to_table_data(component)
        if component.modified:
            raise ValueError(f'{component.id} is being upserted in a modified state')
        return finance_model_to_raw_table_data(component) # pyright: ignore[reportArgumentType]

    @override
    def upsert_component(
        self,
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent], 
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        if isinstance(component, NewsegsFinanceInterface) or isinstance(component, Sequence) and all(isinstance(x, NewsegsFinanceInterface) for x in component):
            return super().upsert_component(component, force, tbl)
        else:
            return self._component_provider.upsert_component(component, force, tbl)

    @override
    def _delete_one_component(
        self, 
        component_id: str,
        ignore_ids: list[str] = [],
    ) -> None:
        # Assume that we are dealing only with members of the fm_configs table

        # Any metamodel configurations using this model must be identified
        get_mm_count_stmt = (
            sa.select(sa.func.count())
            .select_from(tbls.metamodels)
            .where(
                sa.and_(
                    tbls.metamodels.c.id.not_in(ignore_ids),
                    (
                        (tbls.metamodels.c.fm_config_id == component_id)
                    )
                )
            )
        )

        # Child components should be identified and subsequently deleted, where appropriate
        get_child_component_id_stmt = (
            sa.select(
                self._table.c.financedata_config_id,
                self._table.c.table_config_id,
            )
            .where(self._table.c.id == component_id)
        )

        del_stmt = (
            self._table.delete()
            .where(self._table.c.id == component_id)
        )

        child_ids = []
        with self._get_engine().connect() as conn:
            for trial_stmt in (
                get_mm_count_stmt,
            ):
                count = conn.execute(trial_stmt).scalar()
                if count:
                    raise DependentObjectsExistError(f'Cannot delete - dependents exist for energy model {component_id}')

            # Get child ids
            row = conn.execute(get_child_component_id_stmt).fetchone()
            if row:
                child_ids = [x for x in row if x]

            # Delete model
            conn.execute(del_stmt)
            conn.commit()

        # Delete children
        _ = self._component_provider.delete_component(child_ids)


class FromDatabaseNewsegsMetamodelProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.metamodels
        self._em_provider = FromDatabaseNewsegsEMProvider(get_engine)
        self._fm_provider = FromDatabaseNewsegsFMProvider(get_engine)
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)
        # This may be overwritten - e.g. by an enclosing ProjectProvider
        self.variable_provider = FromDatabaseVariableProvider(get_engine)

        self._metamodel_variable_jct = tbls.metamodel_variables

    @override
    def _assign_updated_child_uids(self, obj, row):
        super()._assign_updated_child_uids(obj, row)
        if isinstance(obj, NewsegsMetaModel):
            obj._model_id = row.em_config_id
            obj._finance_id = row.fm_config_id
            obj._component_ids['table_config'] = row.table_config_id

            var_stmt = (
                sa.select(
                    tbls.variable_configs.c.varid,
                    tbls.variable_configs.c.id,
                )
                .select_from(self._metamodel_variable_jct)
                .join(
                    tbls.variable_configs,
                    self._metamodel_variable_jct.c.variable_config_id == tbls.variable_configs.c.id,
                )
                .where(self._metamodel_variable_jct.c.metamodel_id == obj.id)
            )
            with self._get_engine().connect() as conn:
                result = conn.execute(var_stmt)
                var_mapping = {
                    row[0]: row[1] for row in result
                }
                # To keep order, try to use the existing order
                used_keys = []
                var_ids = []
                for x in obj.variable_ids:
                    k = x['varid']
                    uid = var_mapping.get(k)
                    if uid:
                        var_ids.append({
                            'varid': k,
                            'uid': uid
                        })
                        used_keys.append(k)
                used_keys = set(used_keys)
                for k in var_mapping.keys():
                    if not k in used_keys:
                        var_ids.append({
                            'varid': k,
                            'uid': var_mapping[k]
                        })
                
                obj._variable_ids = tuple(var_ids)

        return obj

    @override
    def _reattach_children(self, obj):
        obj = super()._reattach_children(obj)
        obj.reattach_em(self._em_provider)
        obj.reattach_fm(self._fm_provider)
        obj.reattach_components(self._component_provider)
        # Do not reattach variables here - wait until the project does it.
        return obj

    @override
    def _create_duplicate_component(self, original: NewsegsComponent) -> NewsegsComponent:
        new =  super()._create_duplicate_component(original)
        if isinstance(original, NewsegsMetaModel):
            new.model = cast(NewsegsModel, self._em_provider.duplicate_component(new._model_id))
            new.finance = cast(NewsegsFinance, self._fm_provider.duplicate_component(new._finance_id))
            # Worth double checking that model is set on finance
            new.finance.set_model(new.model, dirty = False)
            new.variables = {k: v for k, v in original.variables.items()}
        return new

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsMetaModel):
            return super()._component_to_table_data(component)
        if component.modified:
            raise ValueError(f'{component.id} is being upserted in a modified state')
        return metamodel_to_raw_table_data(component)

    def _set_metamodel_variable_junction(self, metamodel: NewsegsMetaModel):
        clear_statement = (
            self._metamodel_variable_jct.delete()
            .where(
                self._metamodel_variable_jct.c.metamodel_id == metamodel.id
            )
        )
        new_variable_entries = [
            {
                'metamodel_id': metamodel.id,
                'variable_config_id': var['uid']
            } for var in metamodel.variable_ids
        ]
        with self._get_engine().begin() as conn:
            conn.execute(clear_statement)

            if new_variable_entries:
                conn.execute(
                    self._metamodel_variable_jct.insert(),
                    new_variable_entries
                )
        
    @override
    def upsert_component(
        self,
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent],
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        if isinstance(component, NewsegsComponent):
            if isinstance(component, NewsegsMetaModel):
                rval = super().upsert_component(component, force, tbl)
                if component.model:
                    self._em_provider.upsert_component(component.model, force)
                if component.finance:
                    self._fm_provider.upsert_component(component.finance, force)
                for v in component.variables.values():
                    self.variable_provider.upsert_variable(v)
                self._set_metamodel_variable_junction(component)
                return rval
            elif isinstance(component, NewsegsModelInterface):
                return self._em_provider.upsert_component(component, force, tbl)
            elif isinstance(component, NewsegsFinanceInterface):
                return self._fm_provider.upsert_component(component, force, tbl)
            else:
                return self._component_provider.upsert_component(component, force, tbl)
        else:
            metamodel_indices = []
            model_indices = []
            finance_indices = []
            component_indices = []
            for i, comp in enumerate(component):
                if isinstance(comp, NewsegsMetaModel):
                    metamodel_indices.append(i)
                elif isinstance(comp, NewsegsModelInterface):
                    model_indices.append(i)
                elif isinstance(comp, NewsegsFinanceInterface):
                    finance_indices.append(i)
                else:
                    component_indices.append(i)

            if metamodel_indices:
                for idx in metamodel_indices:
                    comp = component[idx]
                    self.upsert_component(comp, force, tbl)
            if model_indices:
                self._em_provider.upsert_component(
                    [x for i, x in enumerate(component) if i in model_indices],
                    force,
                    tbl
                )
            if finance_indices:
                self._fm_provider.upsert_component(
                    [x for i, x in enumerate(component) if i in finance_indices],
                    force,
                    tbl
                )
            if component_indices:
                self._component_provider.upsert_component(
                    [x for i, x in enumerate(component) if i in component_indices],
                    force,
                    tbl
                )

    @override
    def _delete_one_component(
        self, 
        component_id: str, 
        ignore_ids: list[str] = []
    ) -> None:
        # Assume that we are dealing only with members of the metamodels table

        # Identify associated EM for deletion
        get_em_id_stmt = (
            sa.select(
                self._table.c.em_config_id
            )
            .where(self._table.c.id == component_id)
        )

        get_fm_id_stmt = (
            sa.select(
                self._table.c.fm_config_id
            )
            .where(self._table.c.id == component_id)
        )

        get_child_component_id_stmt = (
            sa.select(
                self._table.c.table_config_id
            )
            .where(self._table.c.id == component_id)
        )

        # Delete entries in junction tables
        # Note that we will not delete orphan variables, as these are considered managed by the project.
        # It is recommended that the project performs a sweep after metamodel deletion.
        del_proj_mm_stmt = (
            tbls.project_metamodels.delete()
            .where(tbls.project_metamodels.c.metamodel_id == component_id)
        )

        del_mm_var_stmt = (
            tbls.metamodel_variables.delete()
            .where(tbls.metamodel_variables.c.metamodel_id == component_id)
        )

        del_mm_stmt = (
            self._table.delete()
            .where(self._table.c.id == component_id)
        )

        em_ids = []
        fm_ids = []
        child_ids = []
        with self._get_engine().connect() as conn:
            # No trials, can get on with finding children
            row = conn.execute(get_em_id_stmt).fetchone()
            if row:
                em_ids = [x for x in row if x]

            row = conn.execute(get_fm_id_stmt).fetchone()
            if row:
                fm_ids = [x for x in row if x]

            row = conn.execute(get_child_component_id_stmt).fetchone()
            if row:
                child_ids = [x for x in row if x]

            # Delete metamodel
            conn.execute(del_proj_mm_stmt)
            conn.execute(del_mm_var_stmt)
            conn.execute(del_mm_stmt)

            conn.commit()

        # Delete children
        _ = self._em_provider.delete_component(em_ids)
        _ = self._fm_provider.delete_component(fm_ids)
        _ = self._component_provider.delete_component(child_ids)


class FromDatabaseNewsegsProjectProvider(
    FromDatabaseNewsegsComponentProvider,
    NewsegsProjectProviderInterface,
):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.projects
        # The metamodel and variable providers are public for this class
        self.metamodel_provider = FromDatabaseNewsegsMetamodelProvider(get_engine)
        self.variable_provider = FromDatabaseVariableProvider(get_engine)
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

        self._project_metamodel_jct = tbls.project_metamodels
        self._project_variable_jct = tbls.project_variables

    @override
    def _assign_updated_child_uids(self, obj, row):
        super()._assign_updated_child_uids(obj, row)
        if isinstance(obj, NewsegsProject):
            obj._component_ids['table_config'] = row.table_config_id
            obj._component_ids['dsa_config'] = row.dsa_component_config_id
            obj._component_ids['psa_config'] = row.psa_component_config_id
            # No need to update the focussed metamodel - as this is
            # stored as an int, it should not be impacted so long
            # as the order of metamodels is consistent.

            # The row is not enough for us to reassign metamodel uids
            # - need to go to the junction table
            metamodel_ids = self.list_project_metamodel_ids(obj.id)
            obj._metamodel_ids = metamodel_ids

            # Similarly, variable uids may have been modified.
            stmt = (
                sa.select(
                    tbls.variable_configs.c.varid,
                    tbls.variable_configs.c.id,
                )
                .select_from(self._project_variable_jct)
                .join(
                    tbls.variable_configs,
                    self._project_variable_jct.c.variable_config_id == tbls.variable_configs.c.id,
                )
                .where(self._project_variable_jct.c.project_id == obj.id)
            )
            with self._get_engine().connect() as conn:
                result = conn.execute(stmt)
                vrus = {}
                for row in result:
                    varid = row[0]
                    uid = row[1]
                    if not varid in vrus:
                        vrus[varid] = []
                    vrus[varid].append(uid)
            obj._variable_recovery_uids = vrus
        return obj

    @override
    def _reattach_children(self, obj):
        obj = super()._reattach_children(obj)
        obj.reattach_components(self._component_provider)
        obj.reattach_variables(self.variable_provider)
        obj.reattach_metamodels(self.metamodel_provider)
        return obj

    def _create_duplicate_component(self, original: NewsegsComponent) -> NewsegsComponent:
        new = super()._create_duplicate_component(original)
        if isinstance(new, NewsegsProject):
            new._variables_by_uid.clear()
            var_mapping = {}
            for var_uid in original._variables_by_uid.keys():
                new_var = self.variable_provider.duplicate_variable(var_uid)
                var_mapping[var_uid] = new_var.id
                new.add_variable(new_var)
            new.metamodels = [self.metamodel_provider.duplicate_component(x) for x in new._metamodel_ids]
            for mm in new.metamodels:
                old_variables = mm.variable_ids
                new_variables = tuple(
                    (
                        {
                            'varid': x['varid'],
                            'uid': var_mapping[x['uid']]
                        }
                        for x in old_variables
                    )
                )
                mm.variables = {} # Just in case
                mm._variable_ids = new_variables
                mm.reattach_variables(new)
            
        return new
    
    @override
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsComponent:
        if isinstance(component_id, str):
            orig = self.get_component(component_id)
        else:
            orig = component_id
        if isinstance(orig, NewsegsMetaModel):
            return self.metamodel_provider.duplicate_component(orig)
        elif isinstance(orig, Variable):
            return self.variable_provider.duplicate_variable(orig.id)
        elif not isinstance(orig, NewsegsProject):
            # Is a normal component
            return self._component_provider.duplicate_component(orig)
        else:
            return super().duplicate_component(orig)

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsProject):
            return super()._component_to_table_data(component)
        if component.modified:
            raise ValueError(f'{component.id} is being upserted in a modified state')
        return project_to_raw_table_data(component)

    def _upsert_project(
        self,
        project: NewsegsProject,
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        # Unlike other upsertions, projects require junction tables to be sorted.
        v_to_sync = list(project._variables_by_uid.values())
        vars_modified = any(x.modified for x in v_to_sync)
        self.variable_provider.upsert_variable(v_to_sync)
        if vars_modified:
            project.table_config.revision += 1
        self.metamodel_provider.upsert_component(list(project.metamodels))
        super().upsert_component(project, force, tbl)

        # TODO: Improve this logic and keep track of addition of variables to the project

        # Project - Variable junction
        new_variable_entries = [
            {'project_id': project.id, 'variable_config_id': var_uid}
            for var_uid in project._variables_by_uid.keys()
        ]
        with self._get_engine().begin() as conn:
            # Clear existing entries
            conn.execute(
                self._project_variable_jct.delete()
                .where(
                    self._project_variable_jct.c.project_id == project.id
                )
            )

            # Add new variables
            if new_variable_entries:
                conn.execute(
                    self._project_variable_jct.insert(),
                    new_variable_entries
                )

        # Project - Metamodel junction
        new_metamodel_entries = [
            {
                'project_id': project.id, 
                'metamodel_id': mm.id,
            }
            for mm in project.metamodels
        ]
        with self._get_engine().begin() as conn:
            # Clear existing entries
            conn.execute(
                self._project_metamodel_jct.delete()
                .where(
                    self._project_metamodel_jct.c.project_id == project.id
                )
            )

            # Add new metamodels
            if new_metamodel_entries:
                conn.execute(
                    self._project_metamodel_jct.insert(),
                    new_metamodel_entries
                )

    @override
    def upsert_component(
        self,
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent],
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        if isinstance(component, NewsegsComponent):
            if isinstance(component, NewsegsProject):
                return self._upsert_project(component, force, tbl)
            elif isinstance(component, NewsegsMetaModel):
                return self.metamodel_provider.upsert_component(component, force)
            elif isinstance(component, Variable):
                return self.variable_provider.upsert_variable(component, force)
            else:
                return self._component_provider.upsert_component(component, force, tbl)
        else:
            project_indices = []
            metamodel_indices = []
            variable_indices = []
            component_indices = []
            for i, comp in enumerate(component):
                if isinstance(comp, NewsegsProject):
                    project_indices.append(i)
                elif isinstance(comp, NewsegsMetaModel):
                    metamodel_indices.append(i)
                elif isinstance(comp, Variable):
                    variable_indices.append(i)
                else:
                    component_indices.append(i)
            if project_indices:
                for idx in project_indices:
                    comp = component[idx]
                    self.upsert_component(comp)
            if metamodel_indices:
                self.metamodel_provider.upsert_component(
                    [x for i, x in enumerate(component) if i in metamodel_indices],
                    force
                )
            if variable_indices:
                self.variable_provider.upsert_variable(
                    [x for i, x in enumerate(component) if i in variable_indices], # pyright: ignore[reportArgumentType]
                    force
                )
            if component_indices:
                self._component_provider.upsert_component(
                    [x for i, x in enumerate(component) if i in component_indices],
                    force,
                    tbl
                )

    def _get_project_details_columns(self):
        return (
            self._table.c.id,
            self._table.c.label,
            self._table.c.model_type,
            self._table.c.model_version,
            self._table.c.created_at,
        )

    @override
    def list_projects(
        self,
        model_type: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> pd.DataFrame:
        stmt = sa.select(*self._get_project_details_columns())
        if model_type:
            stmt = stmt.where(self._table.c.model_type == model_type)
        if model_version:
            stmt = stmt.where(self._table.c.model_version == model_version)

        with self._get_engine().connect() as conn:
            odf = pd.read_sql(stmt, conn)
        return odf

    @override
    def recover_session_project(
        self,
        session_id: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> NewsegsProject:
        if session_id:
            stmt = (
                sa.select(self._table.c.id)
                .select_from(tbls.sessions)
                .join(
                    self._table,
                    tbls.sessions.c.active_project_id == self._table.c.id,
                )
                .where(tbls.sessions.c.session_id == session_id)
                .limit(1)
            )
            with self._get_engine().connect() as conn:
                project_id = conn.execute(stmt).scalar_one_or_none()
                if project_id:
                    return self.get_component(project_id)

        projects = self.list_projects(model_type)
        if len(projects):
            return self.get_component(projects['id'].iloc[-1])

        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        if model_type:
            return PROJECT_FACTORIES[model_type]()
        else:
            return PROJECT_FACTORIES[list(PROJECT_FACTORIES.keys())[0]]()

    @override
    def get_session_project_id(
        self, 
        session_id: str | None = None, 
        model_type: str | None = None,
        on_missing: ON_MISSING_OPTION = 'last'
    ) -> str:
        if session_id:
            stmt = (
                sa.select(tbls.sessions.c.active_project_id)
                .where(tbls.sessions.c.session_id == session_id)
                .limit(1)
            )
            with self._get_engine().connect() as conn:
                project_id = conn.execute(stmt).scalar_one_or_none()
                if project_id:
                    # Assert that the project is of the correct type
                    if not model_type:
                        return project_id
                    
                    stmt = (
                        sa.select(self._table.c.model_type)
                        .where(self._table.c.id == project_id)
                        .limit(1)
                    )
                    try:
                        with self._get_engine().connect() as conn:
                            current_proj_type = conn.execute(stmt).scalar_one()
                            if current_proj_type == model_type:
                                return project_id
                    except NoResultFound:
                        return project_id

        # Project not found OR project does not match type
        # For on_missing == 'last', convert to 'create' if no projects available
        if on_missing == 'last':
            project_list = self.list_projects(model_type)
            if len(project_list):
                return project_list['id'].iloc[-1]
            on_missing = 'create'

        match on_missing:
            case 'create':
                from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
                if model_type:
                    factory = PROJECT_FACTORIES.get(model_type, PROJECT_FACTORIES['default'])
                else:
                    factory = PROJECT_FACTORIES[list(PROJECT_FACTORIES.keys())[0]]

                proj = factory()
                self.upsert_component(proj)
                if session_id:
                    self.set_session_project_id(session_id, proj.id)
                
                return proj.id
            case 'none':
                return ''

        return ''

    @override
    def set_session_project_id(self, session_id: str, project_id: str):
        delete_stmt = sa.delete(tbls.sessions).where(tbls.sessions.c.session_id == session_id)
        create_stmt = sa.insert(tbls.sessions).values(dict(session_id = session_id, active_project_id = project_id))

        with self._get_engine().begin() as conn:
            conn.execute(delete_stmt)
            conn.execute(create_stmt)

    @override
    def list_project_snapshots(self, project_id: str) -> pd.DataFrame:
        stmt = (
            sa.select(
                tbls.snapshots.c.snapshot_id,
                tbls.snapshots.c.label,
                tbls.snapshots.c.created_at
            )
            .where(tbls.snapshots.c.project_id == project_id)
        )
        with self._get_engine().connect() as conn:
            return pd.read_sql(stmt, conn)

    def rename_snapshot(
        self,
        snapshot_id: int,
        snapshot_name: str
    ):
        stmt = (
            sa.update(tbls.snapshots)
            .where(tbls.snapshots.c.snapshot_id == snapshot_id)
            .values(label = snapshot_name)
        )

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

    @override
    def _delete_one_component(
        self,
        component_id: str,
        ignore_ids: list[str] = []
    ) -> None:
        # Delete an entire project, including any snapshots

        # Delete snapshots straight away
        _ = db_snapshot.delete_snapshots_for_project(
            self._get_engine(),
            tbls.metadata,
            component_id
        )

        # Find metamodels which are only associated with this project (really, none should have multiple projects)
        find_mm_stmt = (
            sa.select(tbls.project_metamodels.c.metamodel_id)
            .group_by(tbls.project_metamodels.c.metamodel_id)
            .having(
                sa.and_(
                    sa.func.count(sa.distinct(tbls.project_metamodels.c.project_id)) == 1,
                    sa.func.max(tbls.project_metamodels.c.project_id) == component_id
                )
            )
        )

        # Find direct children of this project
        get_child_component_id_stmt = (
            sa.select(
                self._table.c.dsa_component_config_id,
                self._table.c.psa_component_config_id,
                self._table.c.table_config_id,
            )
            .where(self._table.c.id == component_id)
        )

        # Delete junction table values

        # By the time this is executed, it should do nothing
        del_proj_mm_stmt = (
            tbls.project_metamodels.delete()
            .where(tbls.project_metamodels.c.project_id == component_id)
        )

        del_proj_var_stmt = (
            tbls.project_variables.delete()
            .where(tbls.project_variables.c.project_id == component_id)
        )

        del_proj_stmt = (
            self._table.delete()
            .where(self._table.c.id == component_id)
        )

        mm_ids = []
        child_ids = []
        with self._get_engine().connect() as conn:
            mm_ids = [x for x in conn.execute(find_mm_stmt).scalars().all()]

            row = conn.execute(get_child_component_id_stmt).fetchone()
            if row:
                child_ids = [x for x in row if x]

        _ = self.metamodel_provider.delete_component(mm_ids)

        with self._get_engine().begin() as conn:
            conn.execute(del_proj_mm_stmt)
            conn.execute(del_proj_var_stmt)
            conn.execute(del_proj_stmt)

        _ = self._component_provider.delete_component(child_ids)

        _ = self.delete_orphan_variables()

    def delete_orphan_variables(self) -> int:

        referenced_variable_ids = sa.union(
            sa.select(tbls.project_variables.c.variable_config_id),
            sa.select(tbls.metamodel_variables.c.variable_config_id)
        )

        del_stmt = (
            tbls.variable_configs.delete()
            .where(tbls.variable_configs.c.id.not_in(referenced_variable_ids))
        )

        with self._get_engine().begin() as conn:
            result = conn.execute(del_stmt)
            return result.rowcount

    def create_project_snapshot(self, project_id: str, snapshot_label: str) -> int:
        snapshot_id = db_snapshot.generic_snapshot_entity(
            self._get_engine(),
            tbls.metadata,
            'projects',
            project_id,
            snapshot_label,
            project_id
        )
        return snapshot_id

    def load_project_snapshot(self, project_id: str, snapshot_id: int) -> NewsegsProject:
        id_remap = db_snapshot.generic_restore_snapshot(
            self._get_engine(),
            tbls.metadata,
            snapshot_id
        )
        new_project_id = id_remap['projects'][project_id]
        return self.get_project(new_project_id)

    def delete_project_snapshot(self, project_id: str, snapshot_id: int):
        db_snapshot.delete_snapshot(self._get_engine(), tbls.metadata, snapshot_id)

    @override
    def list_project_metamodel_ids(self, project_id: str) -> tuple[str, ...]:
        find_mm_stmt = (
            sa.select(self._project_metamodel_jct.c.metamodel_id)
            .where(self._project_metamodel_jct.c.project_id == project_id)
            .order_by(self._project_metamodel_jct.c.created_order)
        )

        with self._get_engine().connect() as conn:
            result = list(conn.execute(find_mm_stmt).scalars())
        #result.reverse()
        return tuple(result)

    @override
    def get_focussed_metamodel_id(self, project_id: str) -> str:
        stmt = (
            sa.select(self._table.c.focussed_metamodel_id)
            .where(self._table.c.id == project_id)
        )
        with self._get_engine().connect() as conn:
            res = conn.execute(stmt).scalar_one()
        return res

class CachedFromDatabaseNewsegsProjectProvider(
    FromDatabaseNewsegsProjectProvider
):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._project_cache = LRUCache(maxsize = 5)
        self._project_last_accessed = {}

    def _get_project_modification_key(self, project_id: str) -> str | None:
        stmt = (
            sa.select(self._table.c.modified_order)
            .where(self._table.c.id == project_id)
        )
        with self._get_engine().connect() as conn:
            res = conn.execute(stmt).scalar()
            if not res:
                raise KeyError(f'Project {project_id} not found.')
            return res

    @override
    def get_project(self, project_id: str) -> NewsegsProject:
        new_modkey = self._get_project_modification_key(project_id)

        print(f'FINDING PROJECT {project_id}')
        if (
            project_id in self._project_last_accessed
            and (new_modkey == self._project_last_accessed[project_id])
            and (project_id in self._project_cache)
        ):
            proj = self._project_cache[project_id]
            print(f'RETURNING PROJECT FROM CACHE {project_id} - revision is {proj.revision}, modified is {proj.chain_modified} and table revision is {proj.table_config.revision}')
            return proj

        proj = super().get_project(project_id)
        print(f'ADDING PROJECT TO CACHE AFTER LOAD {project_id} - revision is {proj.revision}, modified is {proj.chain_modified} and table revision is {proj.table_config.revision}')
        if proj.chain_modified:
            print('Project has been loaded in a modified state')
        self._project_last_accessed[project_id] = new_modkey
        self._project_cache[project_id] = proj
        return proj

    @override
    def upsert_component(self, component: NewsegsComponent | SequenceNotStr[NewsegsComponent], force: bool = False, tbl: sa.Table | None = None) -> None:
        super().upsert_component(component, force, tbl)
        # if isinstance(component, NewsegsProject):
        #     project_id = component.id
        #     print(f'ADDING PROJECT TO CACHE FROM UPSERT {project_id} - revision is {component.revision}, modified is {component.chain_modified} and table revision is {component.table_config.revision}')
        #     modkey = self._get_project_modification_key(project_id)
        #     self._project_last_accessed[project_id] = modkey
        #     self._project_cache[project_id] = component

    @override
    def delete_component(self, component_id: str | SequenceNotStr[str], ignore_ids: list[str] = []) -> list[str]:
        olist = super().delete_component(component_id, ignore_ids)
        # Even if they haven't been deleted, let's delete them from the caches
        component_id = [component_id] if isinstance(component_id, str) else component_id
        for id in component_id:
            try:
                del self._project_last_accessed[id]
            except KeyError:
                pass
            try:
                del self._project_cache[id]
            except KeyError:
                pass

        return olist
