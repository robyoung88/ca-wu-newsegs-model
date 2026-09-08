import copy
import json
from typing import Callable, Optional, Sequence, cast, overload, override

import pandas as pd
import sqlalchemy as sa
from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface

from newsegsmodelapp.backend.db.project import component_to_raw_table_data, finance_model_to_raw_table_data, metamodel_to_raw_table_data, project_to_raw_table_data
from newsegsmodelapp.backend.db.project import energy_model_to_raw_table_data
from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsvariable.variable import Variable


class FromDatabaseNewsegsComponentProvider(
    NewsegsComponentProviderInterface,
    NewsegsComponentPersistenceInterface,
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
        """Given the row for the component, get the live ids for each of the child components."""
        return obj

    def _reattach_children(self, obj):
        """Once the component has updated uids for retrieving children, get them using the necessary providers."""
        return obj

    def _reconstruct_component(self, json_payload, row) -> NewsegsComponent:
        obj = self._component_from_json(json_payload)
        obj = self._assign_updated_child_uids(obj, row)
        obj = self._reattach_children(obj)
        return obj

    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
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
    
    @override
    def duplicate_component(self, component_id: str) -> NewsegsComponent:
        comp1 = self.get_component(component_id)
        comp2 = copy.deepcopy(comp1)
        comp2.id = comp2.generate_new_id()
        compdata = self._component_to_table_data(comp2)
        stmt = self._table.insert().values(compdata)

        with self._get_engine().begin() as conn:
            conn.execute(stmt)

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

        current_revisions = {x.id: x.revision_string for x in component}
        uids = list(current_revisions.keys())

        # Get saved revision if exists
        stmt = (
            sa.select(
                tbl.c.id,
                tbl.c.revision_string
            )
            .where(tbl.c.id.in_(uids))
        )
        engine = self._get_engine()
        with engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()

        saved_revisions = {x.id: x.revision_string for x in rows}
        existing_uids = set(saved_revisions.keys())
        new_inserts = [x for x in uids if x not in existing_uids]
        if not force:
            requires_update = [x for x in existing_uids if current_revisions[x] != saved_revisions[x]]
        else:
            requires_update = existing_uids

        requires_data = set(requires_update)
        requires_data.update(set(new_inserts))

        # First, do the updates, then do the inserts
        for cmp in component:
            if cmp.id in requires_data:
                # TODO: Consider whether to set a rollback here in case we can't access DB
                
                #### Save out all child components ####
                children = cmp.get_components()
                if children:
                    self.upsert_component(children)

                cmp.syncronise()

        cmpdata = {cmp.id: self._component_to_table_data(cmp) for cmp in component if cmp.id in requires_data}

        update_payload = [cmpdata[x] for x in requires_update]
        insert_payload = [cmpdata[x] for x in new_inserts]

        if not (update_payload or insert_payload):
            return
        
        with engine.begin() as conn:
            if update_payload:
                # Cannot use 'id' as the bindparam - rename it
                update_payload = [{'b_id': x.pop('id'), **x} for x in update_payload]
                update_stmt = sa.update(tbl).where(tbl.c.id == sa.bindparam('b_id'))
                conn.execute(update_stmt, update_payload)

            if insert_payload:
                insert_stmt = tbl.insert()
                conn.execute(insert_stmt, insert_payload)


class FromDatabaseNewsegsEMProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.em_configs
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

    @override
    def _assign_updated_child_uids(self, obj, row):
        if isinstance(obj, NewsegsModelInterface):
            obj._component_ids['grid'] = row.grid_config_id
            obj._component_ids['generation'] = row.generation_config_id
            obj._component_ids['consumption_storage'] = row.cs_config_id
            obj._component_ids['table_config'] = row.table_config_id
        return obj

    @override
    def _reattach_children(self, obj):
        obj = super()._reattach_children(obj)
        obj.reattach_components(self._component_provider)
        return obj

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsModelInterface):
            return super()._component_to_table_data(component)

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


class FromDatabaseNewsegsFMProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.fm_configs
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

    @override
    def _assign_updated_child_uids(self, obj, row):
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


class FromDatabaseNewsegsMetamodelProvider(FromDatabaseNewsegsComponentProvider):
    def __init__(self, get_engine: Callable[[], sa.Engine]):
        super().__init__(get_engine)
        self._table = tbls.metamodels
        self._em_provider = FromDatabaseNewsegsEMProvider(get_engine)
        self._fm_provider = FromDatabaseNewsegsFMProvider(get_engine)
        self._component_provider = FromDatabaseNewsegsComponentProvider(get_engine)

    @override
    def _assign_updated_child_uids(self, obj, row):
        if isinstance(obj, NewsegsMetaModel):
            obj._model_id = row.em_config_id
            obj._finance_id = row.fm_config_id
            obj._component_ids['table_config'] = row.table_config_id
        return obj

    @override
    def _reattach_children(self, obj):
        obj = super()._reattach_children(obj)
        obj.reattach_em(self._em_provider)
        obj.reattach_fm(self._fm_provider)
        obj.reattach_components(self._component_provider)
        return obj

    @override
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsMetaModel):
            return super()._component_to_table_data(component)
        return metamodel_to_raw_table_data(component)

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
                    super().upsert_component(comp, force, tbl)
                    if comp.model:
                        self._em_provider.upsert_component(comp.model, force)
                    if comp.finance:
                        self._fm_provider.upsert_component(comp.finance, force)
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
        if isinstance(obj, NewsegsProject):
            obj._component_ids['table_config'] = row.table_config_id

            # The row is not enough for us to reassign metamodel uids
            # - need to go to the junction table
            stmt = (
                sa.select(self._project_metamodel_jct.c.metamodel_id)
                .where(self._project_metamodel_jct.c.project_id == obj.id)
            )
            with self._get_engine().connect() as conn:
                result = conn.execute(stmt)
                metamodel_ids = [str(row[0]) for row in result]
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
                #variable_ids = [str(row[0]) for row in result]
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
    def _component_to_table_data(self, component: NewsegsComponent) -> dict:
        if not isinstance(component, NewsegsProject):
            return super()._component_to_table_data(component)
        return project_to_raw_table_data(component)

    def _upsert_project(
        self,
        project: NewsegsProject,
        force: bool = False,
        tbl: sa.Table | None = None
    ) -> None:
        # Unlike other upsertions, projects require junction tables to be sorted.
        self.variable_provider.upsert_variable(list(project._variables_by_uid.values()))
        self.metamodel_provider.upsert_component(list(project.metamodels))
        super().upsert_component(project, force, tbl)

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
            {'project_id': project.id, 'metamodel_id': mm.id}
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
                return self.metamodel_provider.upsert_component(component, force, tbl)
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
                    force,
                    tbl
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

