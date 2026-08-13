import copy
from typing import Any

from newsegsmodelframework.newsegsgeneration import newsegsgeneration
from newsegsmodelframework.newsegsgeneration import sprakegeneration

_GENERATION_MODULE_CONSTRUCTORS = {
    'SprakeGeneration': sprakegeneration.SprakeGeneration,
}

def generation_module_from_dict(
    config: dict[str, Any]
) -> newsegsgeneration.NewsegsGeneration:
    config = copy.copy(config)
    classname = config.pop('class')
    if classname is None:
        raise ValueError(f'`class` not found in configuration dictionary with keys: {config.keys()}')
    constructor = _GENERATION_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError(f'Generation module constructor not found for {classname}')
    return constructor.from_dict(config)
