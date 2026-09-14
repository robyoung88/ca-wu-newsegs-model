"""
A container and controller for metamodels and variables.

Provides a class which encapsulates multiple NewSEGS metamodels, for multi-way
sensitivity analysis.
"""
from collections import OrderedDict
from typing import Any, Optional, Sequence, override
from useful_types import SequenceNotStr

from newsegsmodelframework.core import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework import newsegsmetamodel
from newsegsmodelframework.core.newsegscomponent import ComponentListProperty, ComponentProperty, NewsegsComponentProviderInterface
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass
from newsegsmodelframework.newsegssensitivity.dsa import DSAComponent
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable.variable import Variable
from newsegsmodelframework.newsegsvariable.variableprovider import InMemoryVariableProvider, RecoverableInMemoryVariableProvider, VariablePersistenceInterface

@revision_dataclass
class NewsegsProjectConfig(DataWithRevision):
    model_type: str = ''
    model_version: str = ''


class NewsegsProject(NewsegsComponent, RecoverableInMemoryVariableProvider):
    """A container and controller for metamodels and variables."""
    
    _name = 'NewSEGS Project'
    _version = 'v0.0.1'
    _id_prefix = 'proj'

    metamodels = ComponentListProperty(oftype = newsegsmetamodel.NewsegsMetaModel)
    dsa_config = ComponentProperty(oftype = DSAComponent)
    psa_config = ComponentProperty(oftype = PSAComponent)
    table_config = ComponentProperty(oftype = TableConfigNewsegsComponent)

    _focussed_metamodel: int = 0

    @override
    def _generate_config(self, *args, **kwargs) -> NewsegsProjectConfig:
        return NewsegsProjectConfig(*args, **kwargs)
    _config: NewsegsProjectConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        metamodels: Optional[Sequence[newsegsmetamodel.NewsegsMetaModel]] = [],
        *args,
        default_variables: Optional[Sequence[Variable]] = [],
        dsa_config: Optional[DSAComponent] = None,
        psa_config: Optional[PSAComponent] = None,
        table_config: Optional[TableConfigNewsegsComponent] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        InMemoryVariableProvider.__init__(self, default_variables)

        self.metamodels = metamodels or []
        if len(self.metamodels):
            if not self.model_type == self.metamodels[0].model.model_type:
                if self.model_type == '':
                    self.model_type = self.metamodels[0].model.model_type
                else:
                    raise TypeError(f'First metamodel of incompatible type; Expected: {self.model_type}; received: {self.metamodels[0].model.model_type}')
            if not self.model_version == self.metamodels[0].model.version:
                if self.model_version == '':
                    self.model_version = self.metamodels[0].model.version
                else:
                    raise TypeError(f'First metamodel of incompatible version; Expected: {self.model_version}; received: {self.metamodels[0].model.version}')

        self.dsa_config = dsa_config or DSAComponent()
        self.psa_config = psa_config or PSAComponent()
        self.table_config = table_config or TableConfigNewsegsComponent()

    @property
    def metamodel_ids(self) -> tuple[str, ...]:
        return tuple(mm.id for mm in self.metamodels)

    def get_focussed_metamodel_index(self) -> int:
        if self._focussed_metamodel >= len(self.metamodels):
            if len(self.metamodels) == 0:
                raise ValueError('No metamodels within project')
            else:
                self._focussed_metamodel = len(self.metamodels) - 1
        return self._focussed_metamodel

    def set_focussed_metamodel_index(self, metamodel_index: int = 0):
        self.set_focussed_metamodel(metamodel_index = metamodel_index)

    def get_focussed_metamodel(self):
        return self.metamodels[self.get_focussed_metamodel_index()]

    def set_focussed_metamodel(self, metamodel_id: Optional[str] = None, metamodel_index: int = 0):
        if metamodel_id:
            for i, mm in enumerate(self.metamodels):
                if mm.id == metamodel_id:
                    self._focussed_metamodel = i
                    return
        self._focussed_metamodel = metamodel_index

    def duplicate_metamodel(self, metamodel_id: str) -> newsegsmetamodel.NewsegsMetaModel:
        try:
            wch = self.metamodel_ids.index(metamodel_id)
        except ValueError:
            raise ValueError(f'Metamodel not found: {metamodel_id}')
        mm = self.metamodels[wch]

        mm2 = newsegsmetamodel.NewsegsMetaModel(
            model = type(mm.model)(mm.model),
            finance = type(mm.finance)(mm.finance),
        )
        mm2._variable_ids = mm.variable_ids
        mm2.reattach_variables(self)

        mm2.table_config.update(mm.table_config.to_dict())

        self.metamodels.append(mm2) # pyright: ignore[reportAttributeAccessIssue]
        return mm2

    def reattach_metamodels(self, provider: NewsegsComponentProviderInterface):
        if not hasattr(self, '_metamodel_ids') or not self._metamodel_ids:
            return
        metamodels = provider.get_component(self._metamodel_ids)
        for i, mm in enumerate(metamodels):
            if not isinstance(mm, newsegsmetamodel.NewsegsMetaModel):
                raise TypeError(f'Component provider did not return a metamodel for id {self._metamodel_ids[i]}, is {type(mm)}')
            mm.reattach_variables(self)
        self.metamodels = metamodels

    def get_metamodel_by_id(self, metamodel_id: str):
        for mm in self.metamodels:
            if mm.id == metamodel_id:
                break
        else:
            raise KeyError(f'Metamodel {metamodel_id} not found for project {self.name}[{self.id}] - available values are {[x.id for x in self.metamodels]}.')
        return mm

    def get_component_attributes(self) -> tuple[str, ...]:
        atts = super().get_component_attributes()
        return ('dsa_config', 'psa_config', 'table_config', *atts)

    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        odict['_metamodel_ids'] = self.metamodel_ids
        odict['_variable_recovery_uids'] = dict()
        for k, v in self._variables_by_varid.items():
            odict['_variable_recovery_uids'][k] = list(v.keys())
        return odict

    def variable_to_store(
            self, 
            store_interface: VariablePersistenceInterface, 
            variable_id: Optional['str | SequenceNotStr[str]'] = None,
            force: bool = False,
        ):
        if isinstance(variable_id, str):
            variable_id = [variable_id, ]
        elif variable_id is None:
            variable_id = list(self._variables_by_uid.keys())

        vars = [self.get_variable(x) for x in variable_id]
        store_interface.upsert_variable(vars, force)
            
NewsegsProject._excluded_attributes = (
    super(NewsegsProject, NewsegsProject)._excluded_attributes 
    + ('_metamodels', '_variables_by_uid', '_variables_by_varid', '_table_config')
)
