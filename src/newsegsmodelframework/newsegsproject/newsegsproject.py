"""
A container and controller for metamodels and variables.

Provides a class which encapsulates multiple NewSEGS metamodels, for multi-way
sensitivity analysis.
"""
from collections import OrderedDict
from typing import Sequence

from newsegsmodelframework.core import newsegscomponent
from newsegsmodelframework import newsegsmetamodel


class NewsegsProject(newsegscomponent.NewsegsComponent):
    """A container and controller for metamodels and variables."""

    model_type: str = 'sprake'
    model_version: str = 'v0.0.1'
    _metamodel_ids: tuple[str, ...] = tuple([])
    _metamodels: tuple[newsegsmetamodel.NewsegsMetaModel, ...] = tuple([])
    
    _name = 'NewSEGS Project'
    _version = 'v0.0.1'
    _id_prefix = 'proj'

    def __init__(
        self,
        metamodels: Sequence[newsegsmetamodel.NewsegsMetaModel],
        model_type: str,
        model_version: str,
    ):
        self.metamodels = metamodels
        # TODO: Allow these to be set by inspection of the metamodels
        self.model_type = model_type
        self.model_version = model_version

    @property
    def metamodels(self) -> tuple[newsegsmetamodel.NewsegsMetaModel,...]:
        return self._metamodels

    @metamodels.setter
    def metamodels(self, metamodels: Sequence[newsegsmetamodel.NewsegsMetaModel]):
        self._metamodels = tuple(x for x in metamodels)
        self._metamodel_ids = tuple(x.id for x in self._metamodels)
        self._revision += 1

    @property
    def metamodel_ids(self) -> tuple[str, ...]:
        return self._metamodel_ids

NewsegsProject._excluded_attributes = super(NewsegsProject, NewsegsProject)._excluded_attributes + ('_metamodels', )
