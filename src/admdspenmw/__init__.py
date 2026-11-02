"""After Diversity Maximum Demand (ADMD) for housing with low carbon technologies.

A Python version of the SP Energy Networks (SP Manweb) public ADMD calculator spreadsheet; see
[the calculator](https://www.spenergynetworks.co.uk/pages/admd_calculator.aspx).

Modules:
    admd: The calculation - a Hamilton dataflow graph whose functions are re-exported by this
        package.
    model_config: Default configuration, inputs and outputs for running the calculation.
"""
from pathlib import Path
PACKAGEDIR = Path(__file__).parent.absolute()

from admdspenmw.admd import *
