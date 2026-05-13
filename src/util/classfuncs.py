"""
Get the reduced class name of the current object
"""
import re

def get_class(obj: object):
    return re.search(r"\.(\w+)\'>$", str(type(obj))).group(1)
