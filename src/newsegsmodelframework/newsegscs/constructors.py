"""Construction of a consumption and storage module from a dictionary.
"""

from newsegsmodelframework.newsegscs import newsegscs
from newsegsmodelframework.newsegscs import sprakecs

_CS_MODULE_CONSTRUCTORS = {
    'SprakeCS': sprakecs.SprakeCS,
}

# REVIEW (redundant?): nothing calls `cs_module_from_dict`; the constructor registries in `core.constructors.registers` do this job.
def cs_module_from_dict(
    ip: dict
) -> newsegscs.NewsegsCS:
    """Create a consumption and storage module from its dictionary.

    The dictionary names the `class` of the module.

    Args:
        ip: Dictionary of the serialised module, including its `class`.

    Returns:
        The consumption and storage module.
    """
    classname = ip.pop('class')
    constructor = _CS_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Consumption and storage module constructor not known: ', classname)
    return constructor.from_dict(ip)
