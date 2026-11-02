"""Constructors module.

TODO: Describe the purpose of the module.
"""
from collections.abc import Mapping

from newsegsmodelframework.newsegscs import newsegscs
from newsegsmodelframework.newsegscs import sprakecs

_CS_MODULE_CONSTRUCTORS = {
    'SprakeCS': sprakecs.SprakeCS,
}

def cs_module_from_dict(
    ip: dict
) -> newsegscs.NewsegsCS:
    """Cs module from dict.

    TODO: Add a description.

    Args:
        ip: TODO.

    Returns:
        TODO.
    """
    classname = ip.pop('class')
    constructor = _CS_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Consumption and storage module constructor not known: ', classname)
    return constructor.from_dict(ip)
