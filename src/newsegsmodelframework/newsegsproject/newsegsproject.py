"""
A container and controller for metamodels and variables.

Provides a class which encapsulates multiple NewSEGS metamodels, for multi-way
sensitivity analysis.
"""
from collections import OrderedDict
from typing import Any, Optional, Sequence, override

from newsegsmodelframework.core import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework import newsegsmetamodel
from newsegsmodelframework.core.newsegscomponent import ComponentListProperty, ComponentProperty
from newsegsmodelframework.core.trackeddata import DataWithRevision
from newsegsmodelframework.newsegssensitivity.dsa import DSAComponent
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable.variable import Variable
from newsegsmodelframework.newsegsvariable.variableprovider import InMemoryVariableProvider


class NewsegsProjectConfig(DataWithRevision):
    ...


class NewsegsProject(NewsegsComponent, InMemoryVariableProvider):
    """A container and controller for metamodels and variables."""
    
    _name = 'NewSEGS Project'
    _version = 'v0.0.1'
    _id_prefix = 'proj'

    metamodels = ComponentListProperty(oftype = newsegsmetamodel.NewsegsMetaModel)
    dsa_config = ComponentProperty(oftype = DSAComponent)
    psa_config = ComponentProperty(oftype = PSAComponent)
    table_config = ComponentProperty(oftype = TableConfigNewsegsComponent)

    @override
    def _generate_config(self, *args, **kwargs) -> NewsegsProjectConfig:
        return NewsegsProjectConfig(*args, **kwargs)
    _config: NewsegsProjectConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        metamodels: Sequence[newsegsmetamodel.NewsegsMetaModel],
        *args,
        default_variables: Optional[Sequence[Variable]] = [],
        dsa_config: Optional[DSAComponent] = None,
        psa_config: Optional[PSAComponent] = None,
        table_config: Optional[TableConfigNewsegsComponent] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        InMemoryVariableProvider.__init__(self, default_variables)

        self.metamodels = metamodels

        self.dsa_config = dsa_config or DSAComponent()
        self.psa_config = psa_config or PSAComponent()
        self.table_config = table_config or TableConfigNewsegsComponent()

    @property
    def metamodel_ids(self) -> tuple[str, ...]:
        return tuple(mm.id for mm in self.metamodels)

    @property
    def model_type(self) -> str:
        if not self.metamodels or not len(self.metamodels):
            return ''
        else:
            return self.metamodels[0].model.model_type

    @property
    def model_version(self) -> str:
        if not self.metamodels or not len(self.metamodels):
            return ''
        else:
            return self.metamodels[0].model.version

    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        odict['_metamodel_ids'] = self.metamodel_ids
        return odict
        
NewsegsProject._excluded_attributes = super(NewsegsProject, NewsegsProject)._excluded_attributes + ('_metamodels', )
