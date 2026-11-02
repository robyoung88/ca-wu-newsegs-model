"""Getting the results of all the metamodels of a project.
"""
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject

def get_result_list(
    result_type: str,
    lproject: LightweightNewsegsProject,
    result_provider: NewsegsResultProviderInterface,
    allow_stale: bool = True
) -> tuple[list, bool]:
    """Get the result of each metamodel of a project, for results that are shown side by side.

    The results are those of the table configuration of the model (or, for finance results, the finance model) of each metamodel.

    Args:
        result_type: The type of the result.
        lproject: The lightweight project.
        result_provider: Provider of results.
        allow_stale: Allow results which are not for the present revision.

    Returns:
        The list of results, and whether any is stale (not for the present revision).
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
    