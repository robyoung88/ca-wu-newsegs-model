"""Construction of a generation module from a dictionary.
"""
import copy
from typing import Any

from newsegsmodelframework.core.constructors import registers
from newsegsmodelframework.newsegsgeneration import newsegsgeneration

# REVIEW (redundant?): nothing calls `generation_module_from_dict`; the constructor registries in `core.constructors.registers` do this job.
def generation_module_from_dict(
    config: dict[str, Any]
) -> newsegsgeneration.NewsegsGeneration:
    """Create a generation module from its dictionary.

    The dictionary names the `class` of the module, which is looked up in the `NewsegsModule` register.

    Args:
        config: Dictionary of the serialised module, including its `class`.

    Returns:
        The generation module.
    """
    config = copy.copy(config)
    classname = config.pop('class')
    if classname is None:
        raise ValueError(f'`class` not found in configuration dictionary with keys: {config.keys()}')
    constructor = registers.get_register('NewsegsModule').get(classname, None)
    if not isinstance(constructor, type) or not issubclass(constructor, newsegsgeneration.NewsegsGeneration):
        raise ValueError(f'Generation module constructor not found for {classname}')
    return constructor.from_dict(config)
