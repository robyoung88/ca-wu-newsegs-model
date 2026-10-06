from typing import Literal


COMPONENT_PREFIXES = {
    'component': 'cmp',
    'em': 'm',
    'fm': 'f',
    'metamodel': 'metam',
    'project': 'proj',
    'variable': 'v',
}

PREFIX_GROUPS = {
    'component_configs': (COMPONENT_PREFIXES['component'],),
    'em_configs': (COMPONENT_PREFIXES['em'],),
    'fm_configs': (COMPONENT_PREFIXES['fm'],),
    'metamodels': (COMPONENT_PREFIXES['metamodel'],),
    'projects': (COMPONENT_PREFIXES['project'],),
    'exclude_variables': tuple(v for k, v in COMPONENT_PREFIXES.items() if k != 'variable'),
}

PREFIX_GROUP_KEY = Literal[
    'component_configs',
    'em_configs',
    'fm_configs',
    'metamodels',
    'projects',
    'exclude_variables',
]
