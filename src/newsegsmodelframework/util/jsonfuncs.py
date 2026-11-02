"""Helpers for JSON.
"""
import json

import numpy as np
import pandas as pd

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder which can encode numpy arrays (as lists) and pandas timestamps (as strings).
    """
    def default(self, obj):
        """Encode objects which JSON cannot.

        Args:
            obj: The object to encode.

        Returns:
            The JSON-serialisable form.
        """
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, pd.Timestamp):
            return str(obj)
        return super().default(obj)
