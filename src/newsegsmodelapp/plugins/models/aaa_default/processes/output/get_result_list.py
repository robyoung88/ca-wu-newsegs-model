"""Get result list module.

TODO: Describe the purpose of the module.
"""
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject

def get_result_list(
    result_type: str,
    lproject: LightweightNewsegsProject,
    result_provider: NewsegsResultProviderInterface,
    allow_stale: bool = True
) -> tuple[list, bool]:
    """Get result list.

    TODO: Add a description.

    Args:
        result_type: TODO.
        lproject: TODO.
        result_provider: TODO.
        allow_stale: TODO.

    Returns:
        TODO.
    """
    is_finance = 'finance' in result_type
    results_list = []
    any_stale = False
    for mm in lproject.metamodels:
        if is_finance:
            component = mm.finance.table_config
        else:
            component = mm.model.table_config
        res, rev = result_provider.get_result(
            result_type,
            component,
            allow_stale
        )
        any_stale = any_stale or rev != component.revision
        # Can't set an attribute on a dict, so need to think of some other way of flagging stale data
        #if res is not None:
        #    setattr(res, '_stale', rev != component.revision)
        results_list.append(res)
    return results_list, any_stale
    