from collections.abc import Mapping

from src.newsegsgeneration import newsegsgeneration
from src.newsegsgeneration import sprakegeneration

_GENERATION_MODULE_CONSTRUCTORS = {
    'SprakeGeneration': sprakegeneration.SprakeGeneration,
}

def generation_module_from_dict(
    ip: Mapping
) -> newsegsgeneration.NewsegsGeneration:
    classname = ip.pop('class')
    constructor = _GENERATION_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Generation module constructor not known: ', classname)
    return constructor.from_dict(ip)
