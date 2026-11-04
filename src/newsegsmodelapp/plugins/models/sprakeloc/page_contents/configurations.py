"""Layout configurations of the pages for the `sprakeloc` model type.

Copies the configuration of each page for the `sprake` model type, so that the pages show the same
navigation, text, and input and result cards. A page with no configuration for a model type falls
back to the page's generic default, which has no cards, so each page must be registered.

The input fields, feedback graphs, postprocesses and tables need no registration: those of the
`sprake` model type are also registered as the defaults, which other model types fall back to.
"""
import copy

from newsegsmodelapp import registers

# Ensure the `sprake` configurations are registered before they are copied
from ...aaa_default.page_contents import configurations as _sprake_configurations  # noqa: F401

_SOURCE_MODEL_TYPE = 'sprake'
_MODEL_TYPE = 'sprakeloc'

for _page_type in ('landing', 'site-config', 'dsa', 'psa'):
    config = copy.copy(registers.get_page_layout_configuration(_page_type, _SOURCE_MODEL_TYPE))
    config.model_type = _MODEL_TYPE
    if _page_type == 'landing':
        config.head_text = 'Sprake Location Aware Model'  # pyright: ignore[reportAttributeAccessIssue]
    registers.add_page_layout_configuration(config, _page_type, _MODEL_TYPE)
