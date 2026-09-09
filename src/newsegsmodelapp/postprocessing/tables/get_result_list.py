from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject


def get_result_list(
    result_type: str,
    project: NewsegsProject,
    result_provider: NewsegsResultProviderInterface,
    allow_stale: bool = True
):
    is_finance = 'finance' in result_type
    results_list = []
    for mm in project.metamodels:
        if is_finance:
            component = mm.finance.table_config
        else:
            component = mm.model.table_config
        res, rev = result_provider.get_result(
            result_type,
            component,
            allow_stale
        )
        # Can't set an attribute on a dict, so need to think of some other way of flagging stale data
        #if res is not None:
        #    setattr(res, '_stale', rev != component.revision)
        results_list.append(res)
    return results_list
    