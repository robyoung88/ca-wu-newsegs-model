"""Helpers for running the ADMD calculation (`admdspenmw`) with Hamilton.
"""
from functools import cache

from hamilton import registry; registry.disable_autoload
from hamilton import driver

import admdspenmw as admdcalc
from admdspenmw.model_config import default_model_config

@cache
def _get_default_admd_model_driver() -> driver.Driver:
    return (
        driver.Builder()
            .with_config(default_model_config)
            .with_modules(admdcalc)
            .build()
    )

def get_admd_model_driver(conf:dict) -> driver.Driver:
    """Get a Hamilton driver of the ADMD calculation (`admdspenmw`) with a configuration.

    The driver of the default configuration is cached.

    Args:
        conf: Hamilton configuration.

    Returns:
        The driver.
    """
    if conf == default_model_config:
        return _get_default_admd_model_driver()
    else:
        return (
            driver.Builder()
                .with_config(conf)
                .with_modules(admdcalc)
                .build()
        )
