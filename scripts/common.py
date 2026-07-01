"""
Functionality and imports common to all scripts
"""
import sys
import os

def setup_script_env():
    """
    Modify environment variables, e.g. path, to run scripts.
    """

    # Add src folder to path
    curdir = os.path.dirname(__file__)
    src_path = os.path.join(
        os.path.abspath(os.path.join(curdir, os.pardir)),
        'src'
    )
    sys.path.append(src_path)
