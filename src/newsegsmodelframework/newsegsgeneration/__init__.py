"""Provides base class and implementations of NewsegsGeneration."""
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import NewsegsGeneration, NewsegsGenerationConfig, get_generation_meters
from newsegsmodelframework.newsegsgeneration.sprakegeneration import SprakeGeneration, SprakeGenerationConfig
__all__ = [
    'NewsegsGeneration',
    'NewsegsGenerationConfig',
    'SprakeGeneration',
    'SprakeGenerationConfig',
    'get_generation_meters',
]
