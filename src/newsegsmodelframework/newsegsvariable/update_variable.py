from newsegsmodelframework.newsegsvariable.variable import Param, ScalarParam, Variable


def update_variable(
    var: Variable,
    parameter_index: int,
    vector_location: int,
    value: ScalarParam
) -> tuple[bool, bool, bool, bool, tuple[Param,...]]:
    """
    Update the addressed variable with the new value.

    The Variable is addressed by {section}.{key}.{subindex} in the 
    .variables OrderedDict. After identifying the variable, the nominated 
    parameter index is updated with the scalar value; if the parameter is
    an array type, it is addressed by its location in the flattened array
    using the vector_location.

    Args:
        section: Interface section.
        key: Variable specifier.
        subindex: Index of multiple instances of specified Variable.
        parameter_index: Index of metaparameter within Variable to update.
        vector_location: Index of scalar metaparameter within flattened array of array-type parameter.
        value: Value with which to update metaparameter.

    Returns:
        - bool - The parameter has been set
        - bool - The deterministic value of the Variable has been impacted
        - bool - The DSA value(s) of the Variable has/have been impacted
        - bool - The PSA values(s) of the Variable has/have been impacted
        - tuple[Param, ...] - The set of parameters now held by the Variable
    """
    old_params = var.parameters
    old_value = var.deterministic_value
    old_std = var.get_std()
    old_dsa_low = var.get_dsa_value('lower', True)
    old_dsa_high = var.get_dsa_value('upper', True)
    is_ok, new_params = var.set_single_parameter(value, parameter_index, vector_location)

    if not is_ok:
        var.set_parameters(*old_params)
        return False, True, True, True, old_params
    
    if var.dsa_show:
        try:
            dsa_changed = (
                (var.get_dsa_value('lower', True) != old_dsa_low)
                or (var.get_dsa_value('upper', True) != old_dsa_high)
            )
        except TypeError:
            var.set_parameters(*old_params)
            return False, True, True, True, old_params
    else:
        dsa_changed = False
        
    new_value = var.deterministic_value

    if var.psa_show:
        new_std = var.get_std()
        psa_changed = (
            old_value != new_value
            or old_std != new_std
        )
    else:
        psa_changed = False

    det_changed = old_value != new_value

    return is_ok, det_changed, dsa_changed, psa_changed, new_params
