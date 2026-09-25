
from typing import cast

from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.components.variable_dash_component import vdc as var_dc

def create_psa_input(
    var: variable.Variable
):
    if not var.psa_show:
        return None
    match var.distribution.distribution:
        case 'constant':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_constant
        case 'numeric_constant':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_constant
        case 'normal':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_normal
        case 'beta':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_beta
        case 'gamma':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_gamma
        case _:
            raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
        
    if is_scalar:
        var = cast(variable.NumericScalarVariable, var)
        return creation_func(var)
    else:
        raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
    