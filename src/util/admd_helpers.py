import os
from pathlib import Path
libdir = Path(__file__).parent.parent.absolute()
os.chdir(libdir)
from hamilton import registry; registry.disable_autoload
from hamilton import driver
import src.admdspenmw as admdcalc
from src.admdspenmw.model_config import default_model_config, default_model_inputs, default_model_outputs
import numpy as np
import pandas as pd
from functools import cache

@cache
def _get_default_admd_model_driver() -> driver.Driver:
    return (
        driver.Builder()
            .with_config(default_model_config)
            .with_modules(admdcalc)
            .build()
    )

def get_admd_model_driver(conf:dict) -> driver.Driver:
    if conf == default_model_config:
        return _get_default_admd_model_driver()
    else:
        return (
            driver.Builder()
                .with_config(conf)
                .with_modules(admdcalc)
                .build()
        )
