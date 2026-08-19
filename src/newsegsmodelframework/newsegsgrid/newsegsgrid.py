"""Provides abstract base class for NewSEGS Grid Module"""

from newsegsmodelframework.core import NewsegsModule

class NewsegsGrid(NewsegsModule):
    """Abstract base class for NewSEGS Grid Module"""
    module_type = 'grid'
