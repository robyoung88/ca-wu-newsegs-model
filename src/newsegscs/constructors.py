from collections.abc import Mapping

from newsegscs import newsegscs
from newsegscs import sprakecs

_CS_MODULE_CONSTRUCTORS = {
    'SprakeCS': sprakecs.SprakeCS,
}

def cs_module_from_dict(
    ip: Mapping
) -> newsegscs.NewsegsCS:
    classname = ip.pop('class')
    constructor = _CS_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Consumption and storage module constructor not known: ', classname)
    return constructor.from_dict(ip)
