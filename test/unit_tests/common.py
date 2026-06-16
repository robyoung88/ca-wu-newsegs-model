"""
Functionality and imports common to all unit tests
"""
import sys
import re
import os

def setup_test_env():
    """
    Modify environment variables, e.g. path, to run tests.
    """

    # Add src folder to path
    curdir = os.path.dirname(__file__)
    clean_path = os.path.normpath(curdir)
    marker = os.sep + 'test' + os.sep
    marker_index = clean_path.find(marker)
    if marker_index != -1:
        proj_path = clean_path[:marker_index]
    else:
        proj_path = os.path.dirname(os.path.dirname(curdir))
    src_path = os.path.join(
        proj_path,
        'src'
    )
    sys.path.append(src_path)
