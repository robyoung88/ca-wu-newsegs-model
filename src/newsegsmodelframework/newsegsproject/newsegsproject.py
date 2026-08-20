"""
A container and controller for metamodels and variables.

Provides a class which encapsulates multiple NewSEGS metamodels, for multi-way
sensitivity analysis.
"""
from collections import OrderedDict
from typing import Sequence

from newsegsmodelframework.core import newsegscomponent
from newsegsmodelframework import newsegsmetamodel
from newsegsmodelframework.newsegssensitivity.dsa import DSAComponent
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent


class NewsegsProject(newsegscomponent.NewsegsComponent):
    """A container and controller for metamodels and variables."""

    model_type: str = 'sprake'
    model_version: str = 'v0.0.1'
    _metamodel_ids: tuple[str, ...] = tuple([])
    _metamodels: tuple[newsegsmetamodel.NewsegsMetaModel, ...] = tuple([])
    
    _name = 'NewSEGS Project'
    _version = 'v0.0.1'
    _id_prefix = 'proj'

    _dsa_config: DSAComponent
    _psa_config: PSAComponent
    _table_config: newsegscomponent.TableConfigNewsegsComponent

    def __init__(
        self,
        metamodels: Sequence[newsegsmetamodel.NewsegsMetaModel],
        model_type: str,
        model_version: str,
        **kwargs
    ):
        self.metamodels = metamodels
        # TODO: Allow these to be set by inspection of the metamodels
        self.model_type = model_type
        self.model_version = model_version

        if 'dsa_config' in kwargs:
            self.dsa_config = kwargs['dsa_config']
        else:
            self.dsa_config = DSAComponent()

        if 'psa_config' in kwargs:
            self.psa_config = kwargs['psa_config']
        else:
            self.psa_config = PSAComponent()

        if 'table_config' in kwargs:
            self.table_config = kwargs['table_config']
        else:    
            self.table_config = newsegscomponent.TableConfigNewsegsComponent()

    @property
    def metamodels(self) -> tuple[newsegsmetamodel.NewsegsMetaModel,...]:
        return self._metamodels

    @metamodels.setter
    def metamodels(self, metamodels: Sequence[newsegsmetamodel.NewsegsMetaModel]):
        self._metamodels = tuple(x for x in metamodels)
        self._metamodel_ids = tuple(x.id for x in self._metamodels)
        self._revision += 1

    @property
    def table_config(self) -> newsegscomponent.TableConfigNewsegsComponent:
        return self._table_config

    @table_config.setter
    def table_config(self, table_config: newsegscomponent.TableConfigNewsegsComponent):
        self._table_config = table_config

    @property
    def dsa_config(self) -> DSAComponent:
        return self._dsa_config

    @dsa_config.setter
    def dsa_config(self, dsa_config: DSAComponent):
        self._dsa_config = dsa_config

    @property
    def psa_config(self) -> PSAComponent:
        return self._psa_config

    @psa_config.setter
    def psa_config(self, psa_config: PSAComponent):
        self._psa_config = psa_config

    @property
    def metamodel_ids(self) -> tuple[str, ...]:
        return self._metamodel_ids

NewsegsProject._excluded_attributes = super(NewsegsProject, NewsegsProject)._excluded_attributes + ('_metamodels', )
