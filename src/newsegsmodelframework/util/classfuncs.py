"""Helpers for classes.
"""
import re

def get_class(obj: object):
    """The name of the class of an object.

    Args:
        obj: The object to encode.

    Returns:
        The class name.
    """
    return re.search(r"\.(\w+)\'>$", str(type(obj))).group(1)
