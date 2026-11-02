"""Constants shared by the components.

Attributes:
    CONFIGURATION_UPDATE_TRIGGER_ID: Id of the store which signals that the configuration has changed.
    VARIABLE_PARAMETER_KEYS: Identification keys required to update a single variable parameter.
"""

CONFIGURATION_UPDATE_TRIGGER_ID = 'configuration-update-trigger'

VARIABLE_PARAMETER_KEYS = (
    'section',
    'key',
    'subindex',
    'parameter_index',
    'vector_location'
)
"""Identification keys required to update a single variable parameter."""
