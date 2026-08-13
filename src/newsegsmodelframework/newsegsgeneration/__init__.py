"""Provides base class and implementations of NewsegsGeneration."""
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import NewsegsGeneration, get_generation_meters
from newsegsmodelframework.newsegsgeneration.sprakegeneration import SprakeGeneration
__all__ = ['NewsegsGeneration', 'SprakeGeneration', 'get_generation_meters']
