"""Jsonfuncs module.

TODO: Describe the purpose of the module.
"""
import json

import numpy as np
import pandas as pd

class NumpyEncoder(json.JSONEncoder):
    """Numpy Encoder.

    TODO: Add a description.
    """
    def default(self, obj):
        """Default.

        TODO: Add a description.

        Args:
            obj: TODO.

        Returns:
            TODO.
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        return super().default(obj)
