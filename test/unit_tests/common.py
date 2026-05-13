"""
Functionality and imports common to all unit tests
"""
import sys
import os

def setup_test_env():
    """
    Modify environment variables, e.g. path, to run tests.
    """

    # Add src folder to path
    curdir = os.path.dirname(__file__)
    src_path = os.path.join(
        os.path.dirname(curdir),
        'src'
    )
    sys.path.append(src_path)
