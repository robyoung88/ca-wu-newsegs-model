from collections.abc import Mapping

from src.newsegsgrid import newsegsgrid
from src.newsegsgrid import sprakegrid

_GRID_MODULE_CONSTRUCTORS = {
    'SprakeGrid': sprakegrid.SprakeGrid,
}

def grid_module_from_dict(
    ip: Mapping
) -> newsegsgrid.NewsegsGrid:
    classname = ip.pop('class')
    constructor = _GRID_MODULE_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('Grid module constructor not known: ', classname)
    return constructor.from_dict(ip)
