"""Construction of a grid module from a dictionary.
"""
from collections.abc import Mapping

from newsegsmodelframework.newsegsgrid import newsegsgrid
from newsegsmodelframework.newsegsgrid import sprakegrid

_GRID_MODULE_CONSTRUCTORS = {
    'SprakeGrid': sprakegrid.SprakeGrid,
}

# REVIEW (redundant?): nothing calls `grid_module_from_dict`; the constructor registries in `core.constructors.registers` do this job.
def grid_module_from_dict(
    ip: Mapping
) -> newsegsgrid.NewsegsGrid:
    """Create a grid module from its dictionary.

    The dictionary names the `class` of the module.

    Args:
        ip: Dictionary of the serialised module, including its `class`.

    Returns:
        The grid module.
    """
    classname = ip.pop('class')
    constructor = _GRID_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Grid module constructor not known: ', classname)
    return constructor.from_dict(ip)
