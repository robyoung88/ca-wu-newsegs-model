import copy
import json
from typing import Callable, Optional, Sequence, cast, overload, override

import sqlalchemy as sa
from useful_types import SequenceNotStr

from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface

from newsegsmodelapp.backend.db.project import component_to_raw_table_data, finance_model_to_raw_table_data, metamodel_to_raw_table_data
from newsegsmodelapp.backend.db.project import energy_model_to_raw_table_data
from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

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

        reconstructed_components = [self._component_from_json(row.payload) for row in rows]
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
        return self._component_from_json(row.payload)

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
    def _component_from_json(self, json_payload: str):
        obj = super()._component_from_json(json_payload)
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
    def _component_from_json(self, json_payload: str):
        obj = super()._component_from_json(json_payload)
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
    def _component_from_json(self, json_payload: str):
        obj = super()._component_from_json(json_payload)
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
