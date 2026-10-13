import copy
import json
import threading
from typing import Any, Callable, Mapping, Optional, Sequence, cast, overload, override

from cachetools import LRUCache
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.exc import NoResultFound
from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db import DependentObjectsExistError, db_snapshot
from newsegsmodelapp.backend.db.db_variable_provider import CachedFromDatabaseVariableProvider, FromDatabaseVariableProvider
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightDataHoldingNewsegsComponent, LightweightNewsegsComponent
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, NewsegsComponentManagerInterface

from newsegsmodelapp.backend.db.project import component_to_raw_table_data, finance_model_to_raw_table_data, metamodel_to_raw_table_data, project_to_raw_table_data
from newsegsmodelapp.backend.db.project import energy_model_to_raw_table_data
from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core.trackeddata import RevisionNotifierMixin
from newsegsmodelframework.newsegsfinance.lightweightnewsegsfinance import LightweightNewsegsFinance
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel.lightweightnewsegsmodel import LightweightNewsegsModel
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import ON_MISSING_OPTION, NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsvariable.lightweight_variable import LightweightVariable
from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid
from newsegsmodelframework.newsegsvariable.variableprovider import VariableProviderInterface

class FromDatabaseNewsegsComponentProvider(
    NewsegsComponentManagerInterface
):
    _table = tbls.component_configs

    _lightweight_component_columns = tuple(
        tbls.component_configs.columns[x] for x in (
            'id',
            'revision'
        )
    )

    _lightweight_dataholding_component_columns = tuple(
        tbls.component_configs.columns[x] for x in (
            'id',

            'component_type',
            'component_class',
            'component_version',

            'revision',
        )
    )
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        self._get_engine = get_engine

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
        #if obj.chain_modified:
        #    raise ValueError('Component has been reconstructed with modified children.')
        return obj

    def _reconstruct_lightweight_component(self, row) -> LightweightNewsegsComponent:
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        comp = LightweightNewsegsComponent.from_dict(metadata)
        comp.revision = revision
        comp._syncronise()
        return comp

    def _reconstruct_lightweight_dataholding_component(self, row) -> LightweightDataHoldingNewsegsComponent:
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        comp = LightweightDataHoldingNewsegsComponent.from_dict(metadata)
        comp.revision = revision
        comp._syncronise()
        return comp

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
        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:
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
                rows = conn.execute(stmt)
                reconstructed_components = [self._reconstruct_component(row.payload, row) for row in rows]
        
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)
        
        if not is_sequence:
            if len(reconstructed_components) == 0:
                raise ValueError(f'Component not found: {component_id} in table {self._table}')
            return reconstructed_components[0]

        compmap = {x.id: x for x in reconstructed_components}
        return [compmap[x] for x in component_id]

    def get_lightweight_component(
        self, component_id: str | SequenceNotStr[str]
    ) -> LightweightNewsegsComponent | SequenceNotStr[LightweightNewsegsComponent]:
        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:
            is_sequence = False
            if isinstance(component_id, str):
                stmt = (
                    sa.select(*self._lightweight_component_columns)
                    .where(self._table.c.id == component_id)
                )
            else:
                is_sequence = True
                stmt = (
                    sa.select(*self._lightweight_component_columns)
                    .where(self._table.c.id.in_(component_id))
                )
            with self._get_engine().connect() as conn:
                rows = conn.execute(stmt).fetchall()

            reconstructed_components = [self._reconstruct_lightweight_component(row) for row in rows]
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)

        if not is_sequence:
            return reconstructed_components[0]
        compmap = {x.id:x for x in reconstructed_components}
        return [compmap[x] for x in component_id]

    def get_lightweight_dataholding_component(
        self, component_id: str | SequenceNotStr[str]
    ) -> LightweightDataHoldingNewsegsComponent | SequenceNotStr[LightweightDataHoldingNewsegsComponent]:
        """Get a representation of (a) component(s) with sufficient detail to save results against"""
        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:
            is_sequence = False
            if isinstance(component_id, str):
                stmt = (
                    sa.select(*self._lightweight_dataholding_component_columns)
                    .where(self._table.c.id == component_id)
                )
            else:
                is_sequence = True
                stmt = (
                    sa.select(*self._lightweight_dataholding_component_columns)
                    .where(self._table.c.id.in_(component_id))
                )

            with self._get_engine().connect() as conn:
                rows = conn.execute(stmt).fetchall()

            reconstructed_components = [self._reconstruct_lightweight_dataholding_component(row) for row in rows]
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)
        
        if not is_sequence:
            return reconstructed_components[0]
        compmap = {x.id:x for x in reconstructed_components}
        return [compmap[x] for x in component_id]

    def _create_duplicate_component(self, original: NewsegsComponent) -> NewsegsComponent:
        comp1 = original
        comp2 = copy.deepcopy(comp1)
        comp2.anonymise_ids()
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

    def _expand_component_sequence(self, component) -> list:
        components = []
        if isinstance(component, NewsegsComponent) and not isinstance(component, Variable):
            components.append(component)
        elif isinstance(component, Mapping):
            for v in component.values():
                if isinstance(v, NewsegsComponent) and not isinstance(v, Variable):
                    components.append(v)
                elif isinstance(v, Mapping) or (not isinstance(v, str) and isinstance(v, Sequence)):
                    components.extend(self._expand_component_sequence(v))
        elif not isinstance(component, str) and isinstance(component, Sequence):
            for v in component:
                if isinstance(v, NewsegsComponent) and not isinstance(v, Variable):
                    components.append(v)
                elif isinstance(v, Mapping) or (not isinstance(v, str) and isinstance(v, Sequence)):
                    components.extend(self._expand_component_sequence(v))
        return components

    def upsert_children(self, component: NewsegsComponent, force: bool = False):
        # Expect to override this for different types of component
        # to deal with different tables
        component_children = component.get_components(component_group= 'component_configs')
        if component_children:
            self.upsert_component(component_children, force = force)
        
    @override
    def upsert_component(
        self, 
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent], 
        force: bool = False,
        tbl: Optional[sa.Table] = None
    ) -> None:
        if tbl is None:
            tbl = self._table
        component = self._expand_component_sequence(component)

        if len(component) == 0:
            return

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
            # TODO: Remove this logic - all revision handling should be outside of the provider
            # If the object exists and has a matching version number but its children have been modified
            # then we do a simple bump of the revision number to indicate that downstream results are stale
            requires_revision_increment = []
            # for comp in component:
            #     if comp.id not in new_inserts and comp.id not in requires_update:
            #         if comp.chain_modified:
            #             requires_revision_increment.append(comp.id)
            #             comp.revision += 1
            #             # Update the table config revision if components have been modified.
            #             if hasattr(comp, 'table_config'):
            #                 if not comp.table_config.modified:
            #                     comp.table_config.revision += 1
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
                self.upsert_children(cmp, force = force)

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

        print(f'Inserted {len(insert_payload)} components: {[x.get('id', str(x)) for x in insert_payload]}')
        print(f'Updated {len(update_payload)} components: {[x.get('b_id', str(x)) for x in update_payload]}')
        print(f'Revised {len(rev_payload)} components: {[x.get('b_id', str(x)) for x in rev_payload]}')

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
        component_id: str | SequenceNotStr[str], 
        metadata_id: str, 
        metadata_value: Any,
        increment_revision: bool = True
    ):
        
        pk_col = list(self._table.primary_key.columns)[0]
        update_col = self._table.c[metadata_id]

        if isinstance(component_id, str):
            stmt = (
                sa.update(self._table)
                .where(pk_col == component_id)
            )
        else:
            stmt = (
                sa.update(self._table)
                .where(pk_col.in_(component_id))
            )

        if increment_revision and not metadata_id == 'revision':
            changed = sa.or_(
                update_col.is_distinct_from(metadata_value)
            )
            stmt = stmt.values(
                revision= sa.case(
                    (changed, self._table.c.revision + 1),
                    else_ = self._table.c.revision
                ),
                **{update_col.name: metadata_value}
            )
        else:
            stmt = stmt.values(
                **{update_col.name: metadata_value}
            )

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        return

    def increment_revision(
        self,
        component_id: str | SequenceNotStr[str]
    ):
        """Increment revision by one on nominated components"""
        pk_col = list(self._table.primary_key.columns)[0]

        if isinstance(component_id, str):
            stmt = (
                sa.update(self._table)
                .where(pk_col == component_id)
            )
        else:
            stmt = (
                sa.update(self._table)
                .where(pk_col.in_(component_id))
            )
        stmt = stmt.values(revision = self._table.c.revision + 1)

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

        try:
            self.invalidate_cache_for_component(component_id)
        except AttributeError:
            pass

        return

class FromDatabaseNewsegsEMProvider(FromDatabaseNewsegsComponentProvider):
    _table = tbls.em_configs

    _lightweight_component_columns = tuple(
        tbls.em_configs.columns[x] for x in (
            'id',

            'label',
            'model_type',
            
            'modeldata_config_id',
            'table_config_id',
            'grid_config_id',
            'generation_config_id',
            'cs_config_id',

            'revision'
        )
    )

    def _create_component_provider(self) -> NewsegsComponentManagerInterface:
        return FromDatabaseNewsegsComponentProvider(self._get_engine)

    def __init__(
        self, *args, 
        component_provider: Optional[NewsegsComponentManagerInterface] = None, 
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._component_provider = component_provider if component_provider else self._create_component_provider()

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
    def _reconstruct_lightweight_component(self, row):
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        metadata['name'] = metadata.pop('label')
        child_ids = [
            metadata.pop(x) for x in (
                'modeldata_config_id',
                'table_config_id',
                'grid_config_id',
                'generation_config_id',
                'cs_config_id',
            )
        ]
        child_components = {
            k:v for k, v in zip(
                (
                    'model_data',
                    'table_config',
                    'grid',
                    'generation',
                    'consumption_storage'
                ),
                self._component_provider.get_lightweight_component(child_ids)
            )
        }
        metadata.update(child_components)
        comp = LightweightNewsegsModel.from_dict(metadata)
        comp.revision = revision
        comp._syncronise()
        return comp

    def get_lightweight_em(
            self, model_id: str | SequenceNotStr[str]
        ) -> LightweightNewsegsModel | SequenceNotStr[LightweightNewsegsModel]:
        return self.get_lightweight_component(model_id)
    
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
    _table = tbls.fm_configs

    _lightweight_component_columns = tuple(
        tbls.fm_configs.columns[x] for x in (
            'id',

            'financedata_config_id',
            'table_config_id',

            'revision',
        )
    )

    def _create_component_provider(self) -> NewsegsComponentManagerInterface:
        return FromDatabaseNewsegsComponentProvider(self._get_engine)

    def __init__(
        self, *args, 
        component_provider: Optional[NewsegsComponentManagerInterface] = None, 
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._component_provider = component_provider if component_provider else self._create_component_provider()
        
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
    def _reconstruct_lightweight_component(self, row):
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        child_ids = [
            metadata.pop(x) for x in (
                'financedata_config_id',
                'table_config_id',
            )
        ]
        child_components = {
            k:v for k, v in zip(
                (
                    'finance_data',
                    'table_config',
                ),
                self._component_provider.get_lightweight_component(child_ids)
            )
        }
        metadata.update(child_components)
        comp = LightweightNewsegsFinance.from_dict(metadata)
        comp.revision = revision
        comp._syncronise()
        return comp

    def get_lightweight_fm(
        self, finance_id: str | SequenceNotStr[str]
    ) -> LightweightNewsegsFinance | SequenceNotStr[LightweightNewsegsFinance]:
        return self.get_lightweight_component(finance_id)
 
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
    _table = tbls.metamodels
    _metamodel_variable_jct = tbls.metamodel_variables

    _lightweight_component_columns = tuple(
        tbls.metamodels.columns[x] for x in (
            'id',
            'label',

            'table_config_id',
            'em_config_id',
            'fm_config_id',
            'location',

            'revision'
        )
    )

    def _create_variable_provider(self) -> VariableProviderInterface:
        return FromDatabaseVariableProvider(self._get_engine)

    def _create_component_provider(self) -> NewsegsComponentManagerInterface:
        return FromDatabaseNewsegsComponentProvider(self._get_engine)

    def _create_em_provider(self) -> FromDatabaseNewsegsEMProvider:
        return FromDatabaseNewsegsEMProvider(
            self._get_engine, component_provider=self._component_provider
        )

    def _create_fm_provider(self) -> FromDatabaseNewsegsFMProvider:
        return FromDatabaseNewsegsFMProvider(
            self._get_engine, component_provider=self._component_provider
        )

    def __init__(
            self,
            *args,
            variable_provider: Optional[VariableProviderInterface] = None,
            component_provider: Optional[NewsegsComponentManagerInterface] = None,
            em_provider: Optional[FromDatabaseNewsegsEMProvider] = None,
            fm_provider: Optional[FromDatabaseNewsegsFMProvider] = None, # TODO: Make interface
            **kwargs,
        ):
        super().__init__(*args, **kwargs)
        # This may be overwritten - e.g. by an enclosing ProjectProvider
        self.variable_provider = variable_provider if variable_provider else self._create_variable_provider()

        self._component_provider = component_provider if component_provider else self._create_component_provider()

        self._em_provider = em_provider if em_provider else self._create_em_provider()
        self._fm_provider = fm_provider if fm_provider else self._create_fm_provider()

    @override
    def _assign_updated_child_uids(self, obj, row):
        super()._assign_updated_child_uids(obj, row)
        if isinstance(obj, NewsegsMetaModel):
            obj.name = row.label

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
        obj.reattach_components(self._component_provider)
        obj.reattach_em(self._em_provider)
        obj.reattach_fm(self._fm_provider)
        # Do not reattach variables here - wait until the project does it.
        return obj

    @override
    def _reconstruct_lightweight_component(self, row):
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        location = metadata.pop('location')
        metadata['name'] = metadata.pop('label')
        child_ids = [
            metadata.pop(x) for x in (
                'table_config_id',
            )
        ]
        child_components = {
            k:v for k, v in zip(
                (
                    'table_config',
                ),
                self._component_provider.get_lightweight_component(child_ids)
            )
        }
        metadata.update(child_components)
        em_child_ids = [
            metadata.pop(x) for x in (
                'em_config_id',
            )
        ]
        em_child_components = {
            k:v for k, v in zip(
                (
                    'model',
                ),
                self._em_provider.get_lightweight_component(em_child_ids)
            )
        }
        metadata.update(em_child_components)
        fm_child_ids = [
            metadata.pop(x) for x in (
                'fm_config_id',
            )
        ]
        fm_child_components = {
            k:v for k, v in zip(
                (
                    'finance',
                ),
                self._fm_provider.get_lightweight_component(fm_child_ids)
            )
        }
        metadata.update(fm_child_components)
        if location is not None:
            metadata['location'] = Location.from_dict(json.loads(location))
        else:
            metadata['location'] = Location.from_none()
        comp = LightweightNewsegsMetaModel.from_dict(metadata)
        fr0 = comp.finance.revision
        comp.finance.model = comp.model
        comp.finance._revision = fr0
        comp.revision = revision
        comp._chain_syncronise()
        return comp

    @override
    def get_lightweight_component(self, component_id):
        rval = super().get_lightweight_component(component_id)
        
        if isinstance(rval, LightweightNewsegsMetaModel):
            is_sequence = False
            component_id = [component_id]
        else:
            is_sequence = True

        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:
            for idx, comp_id in enumerate(component_id):
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
                    .where(self._metamodel_variable_jct.c.metamodel_id == comp_id)
                )
                with self._get_engine().connect() as conn:
                    result = conn.execute(var_stmt)
                    var_mapping = {
                        row[0]: row[1] for row in result
                    }
                if is_sequence:
                    r0 = rval[idx].revision
                    rval[idx].variables = var_mapping
                    rval[idx]._revision = r0
                else:
                    r0 = rval.revision
                    rval.variables = var_mapping
                    rval._revision = r0
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)

        return rval

    def get_lightweight_metamodel(
        self, metamodel_id: str | SequenceNotStr[str]
    ) -> LightweightNewsegsMetaModel | SequenceNotStr[LightweightNewsegsMetaModel]:
        return self.get_lightweight_component(metamodel_id)

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

    def refresh_metamodel_variable_junction(
        self,
        metamodel: NewsegsMetaModel | LightweightNewsegsMetaModel,
        variables: Sequence[Variable | LightweightVariable]
    ):
        varids = [x.varid if isinstance(x, LightweightVariable) else variable_uid(x) for x in variables]
        if not varids:
            return

        # Create a subquery to find variable_config IDs matching the target varids
        var_config_subquery = (
            sa.select(tbls.variable_configs.c.id)
            .where(tbls.variable_configs.c.varid.in_(varids))
        )
        
        clear_statement = (
            self._metamodel_variable_jct.delete()
            .where(
                sa.and_(
                    self._metamodel_variable_jct.c.metamodel_id == metamodel.id,
                    self._metamodel_variable_jct.c.variable_config_id.in_(var_config_subquery)
                )
            )
        )

        new_entries = [
            {
                'metamodel_id': metamodel.id,
                'variable_config_id': var.id
            }
            for var in variables
        ]
        with self._get_engine().begin() as conn:
            conn.execute(clear_statement)

            if new_entries:
                conn.execute(
                    self._metamodel_variable_jct.insert(),
                    new_entries
                )

    @override
    def upsert_children(self, component, force = False):
        component_children = component.get_components(component_group= 'component_configs')
        if component_children:
            self._component_provider.upsert_component(component_children, force = force)
        
        em_children = component.get_components(component_group = 'em_configs')
        if em_children:
            self._em_provider.upsert_component(em_children, force = force)

        fm_children = component.get_components(component_group = 'fm_configs')
        if fm_children:
            self._fm_provider.upsert_component(fm_children, force = force)
        
    @override
    def upsert_component(
        self,
        component: NewsegsComponent | SequenceNotStr[NewsegsComponent],
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        if isinstance(component, NewsegsComponent):
            if isinstance(component, NewsegsMetaModel):
                # First sync the variables so that the OrderedDict can be syncronised prior to upsert
                self.variable_provider.upsert_variable(list(component.variables.values()))
                component.variables._syncronise() # pyright: ignore[reportAttributeAccessIssue]
                
                rval = super().upsert_component(component, force, tbl)
                # if component.model:
                #     self._em_provider.upsert_component(component.model, force)
                # if component.finance:
                #     self._fm_provider.upsert_component(component.finance, force)
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
    _table = tbls.projects
    _project_metamodel_jct = tbls.project_metamodels
    _project_variable_jct = tbls.project_variables

    _lightweight_component_columns = tuple(
        tbls.projects.columns[x] for x in (
            'id',
            'label',

            'table_config_id',
            'dsa_component_config_id',
            'psa_component_config_id',
            
            'focussed_metamodel_id',

            'revision',
        )
    )

    def _create_variable_provider(self) -> VariableProviderInterface:
        return FromDatabaseVariableProvider(self._get_engine)

    def _create_component_provider(self) -> NewsegsComponentManagerInterface:
        return FromDatabaseNewsegsComponentProvider(self._get_engine)

    # TODO: Make an interface
    def _create_metamodel_provider(self) -> FromDatabaseNewsegsMetamodelProvider:
        return FromDatabaseNewsegsMetamodelProvider(
            self._get_engine,
            variable_provider = self.variable_provider,
            component_provider = self._component_provider,
        )

    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        # The metamodel and variable providers are public for this class
        self.variable_provider = self._create_variable_provider()
        self._component_provider = self._create_component_provider()
        self.metamodel_provider = self._create_metamodel_provider()

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

    @override
    def _reconstruct_lightweight_component(self, row):
        metadata = dict(row._mapping)
        revision = metadata.pop('revision')
        metadata['name'] = metadata.pop('label')
        child_ids = [
            metadata.pop(x) for x in (
                'table_config_id',
                'dsa_component_config_id',
                'psa_component_config_id',
            )
        ]
        child_components = {
            k:v for k, v in zip(
                (
                    'table_config',
                    'dsa_config',
                    'psa_config',
                ),
                self._component_provider.get_lightweight_component(child_ids)
            )
        }
        metadata.update(child_components)
        comp = LightweightNewsegsProject.from_dict(metadata)
        comp.revision = revision
        comp._syncronise()
        return comp

    @override
    def get_lightweight_component(self, component_id):
        rval = super().get_lightweight_component(component_id)
        
        if isinstance(rval, LightweightNewsegsProject):
            is_sequence = False
            component_id = [component_id]
        else:
            is_sequence = True

        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:

            for idx, comp_id in enumerate(component_id):
                metamodel_ids = self.list_project_metamodel_ids(comp_id)
                if is_sequence:
                    r0 = rval[idx].revision
                    rval[idx].metamodels = (
                        self.metamodel_provider.get_lightweight_metamodel(metamodel_ids)
                    )
                    for jdx, mm in enumerate(rval[idx].metamodels):
                        if mm.id == rval[idx].focussed_metamodel_id:
                            rval[idx].focussed_metamodel_index = jdx
                            break
                    rval[idx]._revision = r0
                else:
                    r0 = rval.revision
                    rval.metamodels = (
                        self.metamodel_provider.get_lightweight_metamodel(metamodel_ids)
                    )
                    for jdx, mm in enumerate(rval.metamodels):
                        if mm.id == rval.focussed_metamodel_id:
                            rval.focussed_metamodel_index = jdx
                            break
                    rval._revision = r0
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)
            
        return rval

    @overload
    def get_lightweight_project(
        self, project_id: str
    ) -> LightweightNewsegsProject:
        ...

    @overload
    def get_lightweight_project(
        self, project_id: SequenceNotStr[str]
    ) -> SequenceNotStr[LightweightNewsegsProject]:
        ...

    def get_lightweight_project(
        self, project_id: str | SequenceNotStr[str]
    ) -> LightweightNewsegsProject | SequenceNotStr[LightweightNewsegsProject]:
        return self.get_lightweight_component(project_id)

    def add_variables_to_project(
        self,
        project_id: str,
        variables: Sequence[Variable | LightweightVariable]
    ):
        new_entries = [
            {
                'project_id': project_id,
                'variable_config_id': x.id if not isinstance(x, str) else x
            } 
            for x in variables
        ]
        if new_entries:
            with self._get_engine().begin() as conn:
                conn.execute(
                    self._project_variable_jct.insert(),
                    new_entries
                )

    def remove_variables_from_project(
        self,
        project_id: str,
        variables: Sequence[Variable | LightweightVariable | str]
    ):
        var_uids = [x.id if not isinstance(x, str) else x for x in variables]
        clear_statement = (
            self._project_variable_jct.delete()
            .where(
                sa.and_(
                    self._project_variable_jct.c.project_id == project_id,
                    self._project_variable_jct.c.variable_config_id.in_(var_uids)
                )
            )
        )

        with self._get_engine().begin() as conn:
            conn.execute(clear_statement)

        # Trust to .delete_orphan_variables to clean up the variable_config table
        

    # def _create_duplicate_component(self, original: NewsegsComponent) -> NewsegsComponent:
    #     new = super()._create_duplicate_component(original)
    #     if isinstance(new, NewsegsProject):
    #         new._variables_by_uid.clear()
    #         var_mapping = {} 
    #         for var_uid in original._variables_by_uid.keys():
    #             new_var = self.variable_provider.duplicate_variable(var_uid)
    #             var_mapping[var_uid] = new_var.id
    #             new.add_variable(new_var)
    #         new.metamodels = [self.metamodel_provider.duplicate_component(x) for x in new._metamodel_ids]
    #         for mm in new.metamodels:
    #             old_variables = mm.variable_ids
    #             new_variables = tuple(
    #                 (
    #                     {
    #                         'varid': x['varid'],
    #                         'uid': var_mapping[x['uid']]
    #                     }
    #                     for x in old_variables
    #                 )
    #             )
    #             mm.variables = {} # Just in case
    #             mm._variable_ids = new_variables
    #             mm.reattach_variables(new)
            
    #     return new
    
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

    @override
    def upsert_children(self, component, force = False):
        component_children = component.get_components(component_group= 'component_configs')
        if component_children:
            self._component_provider.upsert_component(component_children, force = force)

        metamodel_children = component.get_components(component_group = 'metamodels')
        if metamodel_children:
            self.metamodel_provider.upsert_component(metamodel_children, force = force)

    def _upsert_project(
        self,
        project: NewsegsProject,
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        # Unlike other upsertions, projects require junction tables to be sorted.
        # v_to_sync = list(project._variables_by_uid.values())
        # vars_modified = any(x.modified or x.soft_dirty for x in v_to_sync)
        # self.variable_provider.upsert_variable(v_to_sync)

        # # As variables have all been upserted, we can sync all the metamodel variable lists
        # for mm in project.metamodels:
        #     mm.variables._syncronise() # pyright: ignore[reportAttributeAccessIssue]
        
        #if vars_modified:
        #    project.revision += 1
        #    project.table_config.revision += 1
        
        # Metamodel upsert happens as part of upsert_children
        #self.metamodel_provider.upsert_component(project.metamodels) # pyright: ignore[reportArgumentType]
        # At this point, the metamodel list can be syncronised
        project.metamodels._syncronise() # pyright: ignore[reportAttributeAccessIssue]
        
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
            proj = PROJECT_FACTORIES[model_type]()
            self.add_component(proj)
            return proj
        else:
            proj = PROJECT_FACTORIES[list(PROJECT_FACTORIES.keys())[0]]()
            self.add_component(proj)
            return proj

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
                self.add_component(proj)
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

    def touch_project(self, project_id: str):
        stmt = (
            sa.update(self._table)
            .where(self._table.c.id == project_id)
            .values(label=self._table.c.label)
        )
        with self._get_engine().connect() as conn:
            conn.execute(stmt)

class CachedFromDatabaseNewsegsProjectProvider(
    FromDatabaseNewsegsProjectProvider
):

    def _create_variable_provider(self) -> VariableProviderInterface:
        return CachedFromDatabaseVariableProvider(self._get_engine)
    
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._project_cache = LRUCache(maxsize = 5)
        self._lightweight_project_cache = LRUCache(maxsize = 10)
        self._project_last_accessed = {}
        # Create a lock to prevent a cache stampede at initial load
        self._lock = threading.Lock()

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

        with self._lock:
            print(f'FINDING PROJECT {project_id}')
            if (
                (project_id in self._project_cache)
                and project_id in self._project_last_accessed
                and (new_modkey == self._project_last_accessed[project_id])
            ):
                proj = self._project_cache[project_id]
                print(f'RETURNING PROJECT FROM CACHE {project_id} - revision is {proj.revision}, modified is {proj.chain_modified} and table revision is {proj.table_config.revision}')
                return proj

            proj = super().get_project(project_id)
            print(f'ADDING PROJECT TO CACHE AFTER LOAD {project_id}')
            print(get_project_critical_state(proj))
            if proj.chain_modified:
                print('Project has been loaded in a modified state')
            self._project_last_accessed[project_id] = new_modkey
            self._project_cache[project_id] = proj
        
        return proj

    @override
    def get_lightweight_project(self, project_id):
        if isinstance(project_id, str):
            is_sequence = False
            project_id = [project_id]
        else:
            is_sequence = True

        with self._lock:
            revisions = self.get_component_metadata(project_id, 'revision')
            rlist = []
            get_list = []
            for id_ in project_id:
                print(f'FINDING LIGHTWEIGHT PROJECT {id_}')
                found_component = False
                if id_ in self._lightweight_project_cache:
                    cmpx = self._lightweight_project_cache[id_]
                    if cmpx.revision == revisions[id_]['revision']:
                        rlist.append(cmpx)
                        print(f'FOUND LIGHTWEIGHT PROJECT {cmpx.id} - revision is {cmpx.revision} and table revision is {cmpx.table_config.revision}')
                        found_component = True
                if not found_component:
                    rlist.append(None)
                    get_list.append(id_)

            if len(get_list) > 0:
                components_from_db = super().get_lightweight_component(get_list)
                jdx = 0
                for idx, id_ in enumerate(rlist):
                    if id_ is None:
                        cmpx = components_from_db[jdx]
                        rlist[idx] = cmpx
                        self._lightweight_project_cache[cmpx.id] = cmpx
                        print(f'ADDING LIGHTWEIGHT PROJECT TO CACHE AFTER LOAD {cmpx.id}')
                        print(get_project_critical_state(cmpx))
                        jdx += 1

        if is_sequence:
            return rlist
        return rlist[0] 

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

    def invalidate_cache_for_component(self, component_id):
        if isinstance(component_id, str):
            component_id = [component_id]
        for id_ in component_id:
            if id_ in self._project_cache:
                del self._project_cache[id_]
            if id_ in self._lightweight_project_cache:
                del self._lightweight_project_cache[id_]

    @override
    def set_component_metadata(
        self, 
        component_id, 
        metadata_id, 
        metadata_value, 
        increment_revision = True,
        invalidate_cache = True
    ):
        super().set_component_metadata(
            component_id, metadata_id, 
            metadata_value, increment_revision
        )
        if invalidate_cache:
            self.invalidate_cache_for_component(component_id)
        

def get_component_critical_state(component):
    return {
        'id': component.id,
        'revision': component.revision,
        'modified': component.modified
    }

def get_observable_critical_state(observable):
    return {
        'revision': observable.revision,
        'modified': observable.modified
    }

def get_project_critical_state(project):
    odict = {}
    odict.update(
        {
            'project': get_component_critical_state(project),
            'project.table_config': get_component_critical_state(project.table_config),
            'project.dsa_config': get_component_critical_state(project.dsa_config),
            'project.psa_config': get_component_critical_state(project.psa_config),
            'project.metamodels_container': get_observable_critical_state(project.metamodels),
        }
    )
    for idx, mm in enumerate(project.metamodels):
        mdl = mm.model
        fnc = mm.finance
        mm_dict = {
            f'metamodel_{idx}': get_component_critical_state(mm),
            f'metamodel_{idx}.table_config': get_component_critical_state(mm.table_config),
            f'model_{idx}': get_component_critical_state(mdl),
            f'model_{idx}.table_config': get_component_critical_state(mdl.table_config),
            f'model_{idx}.grid': get_component_critical_state(mdl.grid),
            f'model_{idx}.generation': get_component_critical_state(mdl.generation),
            f'model_{idx}.consumption_storage': get_component_critical_state(mdl.consumption_storage),
            f'finance_{idx}': get_component_critical_state(fnc),
            f'finance_{idx}.table_config': get_component_critical_state(fnc.table_config),
        }
        odict.update(mm_dict)

    return odict