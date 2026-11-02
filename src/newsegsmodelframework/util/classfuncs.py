"""
Get the reduced class name of the current object
"""
import re

def get_class(obj: object):
    """Get class.

    TODO: Add a description.

    Args:
        obj: TODO.

    Returns:
        TODO.
    """
    return re.search(r"\.(\w+)\'>$", str(type(obj))).group(1)
