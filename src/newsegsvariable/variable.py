from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
import copy
from functools import partial
from typing import Any, cast, Callable, Literal, Sequence, Sized, get_args, Union, overload, override
import warnings

from matplotlib.pylab import Generator
import numpy as np
import numpy.typing as npt
from useful_types import SequenceNotStr

from core import newsegscomponent, serialisation
from core.newsegsfinanceinterface import NewsegsFinanceInterface
from core.newsegsmodelinterface import NewsegsModelInterface
from newsegsstats.dirichlet import fit_dirichlet

ScalarParam = Union[str | int | float]
ScalarNumParam = Union[int | float]
VectorParam = Union[Sequence[ScalarParam], np.ndarray[tuple[int], Any]]
NumericVectorParam = Union[Sequence[ScalarNumParam], np.ndarray[tuple[int], np.dtype[np.float64]]]
type MatrixParam[S: np.generic]  = np.ndarray[tuple[int,int], np.dtype[S]]
type MatrixNumParam = MatrixParam[np.float64]

Value = Union[ScalarParam, VectorParam]
Param = Union[ScalarParam, VectorParam, MatrixNumParam]
ParamList = Union[Param, Sequence[Param]]

ModelType = Union[NewsegsModelInterface, NewsegsFinanceInterface]

VARIABLE_TYPE = Literal[
    'scalar',
    'vector'
]

PARAMETER_TYPE = Literal[
    'scalar',
    'vector',
    'matrix',
]

VARIABLE_DISTRIBUTION = Literal[
    'constant',
    'binomial', # i.e. 0/1 for N trials (use 1 trial for bernoulli)
    'normal',
    'beta',
    'gamma',
    'constant_vector',
    'mvn', # multivariate normal
    'dirichlet', # for simplex i.e. vector of probabilities summing to 1
]

SCALAR_DISTRIBUTIONS = [
    'constant',
    'binomial',
    'normal',
    'beta',
    'gamma'
]

VECTOR_DISTRIBUTIONS = [
    'constant_vector',
    'mvn',
    'dirichlet'
]

VARIABLE_TRANSFORM = Literal[
    'identity',
    'ln'
]

CONFIGURATION_TYPE = Literal[
    'model',
    'finance'
]

DSA_BOUND = Literal[
    'central',
    'lower',
    'upper'
]

DSA_BOUNDS_TYPE = Literal[
    'absolute',
    'offset',
    'relative',
    'interval'
]

def _parameter_validation_default(var: Variable, val: Param):
    return

def _n_values_default(var: Variable):
    if isinstance(var.parameters, str) or not isinstance(var.parameters, Sequence):
        return 1
    p0 = var.parameters[0]
    if isinstance(p0, str) or not isinstance(p0, Sequence):
        return 1
    return len(p0)

def _multiparameter_partial_generation_broadcast(
    parameter: tuple[Param, ...],
    parameter_index: tuple[int, ...],
    current_params: tuple[Param, ...],
) -> tuple[Param, ...] | None:
    if not isinstance(parameter, tuple):
        raise TypeError(f'Expecting `parameter` to be provided as a tuple of parameters, got: {type(parameter)}')
    n_parameters = len(current_params)
    pargs = None
    if len(parameter_index) == n_parameters:
        if set(parameter_index) == set(range(n_parameters)):
            if len(parameter) == 1:
                pargs = (parameter[0],) * n_parameters
            elif len(parameter) == len(parameter_index):
                pargs = list(parameter)                    
                for pidx, pval in zip(parameter_index, parameter):
                    pargs[pidx] = pval
                pargs = tuple(pargs)
            else:
                raise TypeError(f'Mismatched parameter tuple length, expecting {len(parameter_index)}, got {len(parameter)}')
        else:
            raise ValueError(f'`parameter_index` inconsistent with parameterisation of max index {n_parameters-1}: {parameter_index}')
    elif len(parameter_index) > n_parameters or len(parameter_index) == 0:
        raise ValueError(f'`parameter_index` inconsistent with parameterisation of max index {n_parameters-1}: {parameter_index}')
    
    return pargs

# NB - we don't really use the features of a Singleton here, as no Singletons have any instance parameters that are modified.
# In the future, this may be stripped out and the classes re-composed.
class Singleton(type):
    _instances = {}
    def __call__(cls, *args: Any, **kwargs: Any) -> Singleton:
        if cls not in cls._instances:
            cls._instances[cls] = (
                super(Singleton, cls)
                .__call__(*args, **kwargs)
            )
        return cls._instances[cls]

class Parameterisation(metaclass = Singleton):
    """
    A single parameterisation of a distribution.
    """

    names: tuple[str, ...]
    types: tuple[PARAMETER_TYPE, ...]
    defaults: tuple[Param, ...]
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> Sequence[Param]:
        """
        Convert parameters into conventional form.
        """
    
    @classmethod
    @abstractmethod
    def partial_generator(
        cls,
        parameter: tuple[Param, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[Param, ...],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[Param, ...], tuple[Param, ...]]:
        """
        Generate a parameter set given a change of some raw parameters.

        Returns:
            A tuple containing the raw parameters and the conventional parameters.
        """
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return True
    

class TwoParamParameterisation(Parameterisation):
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[ScalarNumParam, ScalarNumParam]:
        ...
    
    @classmethod
    @abstractmethod
    def partial_generator(
        cls,
        parameter: tuple[Param, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[Param, ...],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        ...

class VectorParameterisation(Parameterisation):

    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[VectorParam|MatrixNumParam, ...]:
        ...

    @classmethod
    @abstractmethod
    def partial_generator(
        cls,
        parameter: tuple[Param, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[Param, ...],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[Param, ...], tuple[VectorParam|MatrixNumParam, ...]]:
        ...
        
class Distribution(metaclass = Singleton):
    distribution : VARIABLE_DISTRIBUTION
    parameterisations: Sequence[Parameterisation]
    dsa_possible: bool
    psa_possible: bool
    permitted_dsa_bounds: tuple[DSA_BOUNDS_TYPE,...] = (
        'absolute',
        'relative',
        'offset'
    )

    @classmethod
    def n_values(cls, var: Variable) -> int:
        if (
            isinstance(var.parameters, str) 
            or not isinstance(var.parameters, Sequence)
        ):
            return 1
        p0 = var.parameters[0]
        if isinstance(p0, str) or not isinstance(p0, Sized):
            return 1
        return len(p0)

    @classmethod
    @abstractmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        ...
    
    @classmethod
    @abstractmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        ...
    
    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> Value:
        ...

    @classmethod
    @abstractmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> Value:
        ...
    
    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> Value:
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[Value, Value]:
        ...

    @classmethod
    def change_single_scalar_param(
        cls, 
        var: Variable, 
        parameter_value: ScalarParam,
        parameter_index: int,
        parameter_vector_index: int = 0,
        autoscale = True
    ) -> tuple[tuple[Param, ...], tuple[Param, ...]]:
        """
        When a parameter changes in a user interface, trial that change down into the variable
        """
        current_params = var._raw_parameters
        change_param = current_params[parameter_index]
        prm = cls.parameterisations[var.parameterisation_index]
        if isinstance(change_param, str) or not isinstance(change_param, Sequence) or not isinstance(change_param, np.ndarray):
            new_raw, new_params = prm.partial_generator((parameter_value,), (parameter_index,), current_params, autoscale = autoscale)
            return new_raw, new_params
        elif isinstance(change_param, np.ndarray):
            change_param = copy.copy(change_param)
            change_param.flat[parameter_vector_index] = parameter_value
            new_raw, new_params = prm.partial_generator((change_param,), (parameter_index,), current_params, autoscale = autoscale)
            return new_raw, new_params
        else:
            change_param = copy.copy(change_param)
            change_param[parameter_vector_index] = parameter_value
            new_raw, new_params = prm.partial_generator((change_param,), (parameter_index,), current_params, autoscale = autoscale)
            return new_raw, new_params


class ScalarValuedDistribution(Distribution):
    @classmethod
    def n_values(cls, var: Variable) -> int:
        return 1
    
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        if len(values) > 1 or len(values) < 1:
            raise TypeError(f'Single value expected, got {len(values)}')
        val = values[0]
        if isinstance(val, str):
            return
        elif isinstance(val, Sequence):
            raise TypeError(f'Scalar value expected, is sequence of length {len(val)}')

    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> ScalarParam:
        ...
    
    @classmethod
    def _apply_dsa_bound(
        cls,
        deterministic_value: ScalarParam,
        bound_type: DSA_BOUNDS_TYPE,
        bound_value: ScalarParam,
        transform: tuple[VARIABLE_TRANSFORM]
    ) -> ScalarParam:
        match bound_type:
            case 'relative':
                try:
                    bound_value = float(bound_value)
                except TypeError:
                    raise TypeError(f'bound_value must be numeric for relative bound_type, is {type(bound_value)}')
                
                if bound_value == 1.:
                    return deterministic_value
                elif bound_value == 0.:
                    return 0
                
                if isinstance(deterministic_value, str):
                    raise TypeError('Cannot apply a relative bound_value to a string value')
                
                trans = transform[0]
                out_val = deterministic_value
                if trans == 'ln':
                    out_val = np.log(out_val)
                
                out_val *= bound_value

                if trans == 'ln':
                    out_val = np.exp(out_val)
                
                return out_val
            case 'offset':
                try:
                    bound_value = float(bound_value)
                except TypeError:
                    raise TypeError(f'bound_value must be numeric for offset bound_type, is {type(bound_value)}')
                
                if bound_value == 0:
                    return deterministic_value

                if isinstance(deterministic_value, str):
                    raise TypeError('Cannot apply an offset bound_value to a string value')
                
                trans = transform[0]
                out_val = deterministic_value
                if trans == 'ln':
                    out_val = np.log(out_val)
                
                out_val += bound_value

                if trans == 'ln':
                    out_val = np.exp(out_val)
                
                return out_val
            case 'absolute':
                return bound_value
            case _:
                raise ValueError(f'Unknown bound_type: {bound_type}')

    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarParam:
        if not isinstance(var, ScalarVariable):
            raise TypeError(f'Expected ScalarVariable, got {type(var)}')
        match bound:
            case 'central':
                return var.deterministic_value
            case 'lower':
                return cls._apply_dsa_bound(
                    var.deterministic_value,
                    var.dsa_bounds_type,
                    var.dsa_lower,
                    var.transform
                )
            case 'upper':
                return cls._apply_dsa_bound(
                    var.deterministic_value,
                    var.dsa_bounds_type,
                    var.dsa_upper,
                    var.transform
                )
            case _:
                raise ValueError(f'Unknown DSA bound: {bound}')

    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarParam:
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[ScalarParam, ScalarParam]:
        ...


class NumericScalarValuedDistribution(ScalarValuedDistribution):
    interval_function: Callable[[float, Sequence[ScalarNumParam]], tuple[float, float]]
    permitted_dsa_bounds = (
        'absolute',
        'relative',
        'offset',
        'interval'
    )

    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        if len(values) > 1 or len(values) < 1:
            raise TypeError(f'Single value expected, got {len(values)}')
        val = values[0]
        if isinstance(val, str):
            raise TypeError(f'Numeric value expected, is {type(val)}')
        elif isinstance(val, Sequence):
            raise TypeError(f'Scalar value expected, is sequence of length {len(val)}')

    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        ...

    @classmethod
    def _apply_dsa_bound(
        cls,
        deterministic_value: ScalarParam,
        bound_type: DSA_BOUNDS_TYPE,
        bound_value: ScalarParam,
        transform: tuple[VARIABLE_TRANSFORM],
    ) -> ScalarNumParam:
        if isinstance(deterministic_value, str):
            raise ValueError(f'Numeric deterministic value expected, is {type(deterministic_value)}')
        if isinstance(bound_value, str):
            raise ValueError(f'Numeric bound_value expected, is {type(bound_value)}')
        
        match bound_type:
            case 'relative':
                if bound_value == 1.:
                    return deterministic_value
                elif bound_value == 0.:
                    return 0.
                
                trans = transform[0]
                out_val = deterministic_value
                if trans == 'ln':
                    out_val = np.log(out_val)
                
                out_val *= bound_value

                if trans == 'ln':
                    out_val = np.exp(out_val)
                
                return out_val
            case 'offset':
                trans = transform[0]
                out_val = deterministic_value
                if trans == 'ln':
                    out_val = np.log(out_val)
                
                out_val += bound_value

                if trans == 'ln':
                    out_val = np.exp(out_val)
                
                return out_val
            case 'absolute':
                return bound_value

            case _:
                raise ValueError(f'Unknown bound_type: {bound_type}')
            
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        if var.dsa_bounds_type == 'interval':
            if not isinstance(var, NumericScalarVariable):
                raise TypeError(f'Expected NumericScalarVariable, got {type(var)}')
            
            match bound:
                case 'central':
                    return cast(float, super().dsa_value(var, bound))
                case 'lower':
                    lbound, ubound = cls.interval_function(float(var.dsa_lower), var.parameters)
                    return lbound
                case 'upper':
                    lbound, ubound = cls.interval_function(float(var.dsa_upper), var.parameters)
                    return ubound
                case _:
                    raise ValueError(f'Unknown DSA bounds: {bound}')
            
        return cast(float, super().dsa_value(var, bound))
    
    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarNumParam:
        ...
    
    @classmethod
    def dsa_auto_values(
        cls, 
        var: Variable,
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        if not isinstance(var, NumericScalarVariable):
            raise TypeError(f'Expected var as NumericScalarVariable, got {type(var)}')
        match var.dsa_bounds_type:
            case 'relative':
                return (0.9, 1.1)
            case 'offset':
                lbound, ubound = cls.interval_function(interval, var.parameters)
                return (lbound - var.deterministic_value, ubound - var.deterministic_value)
            case 'absolute':
                lbound, ubound = cls.interval_function(interval, var.parameters)
                return (lbound, ubound)
            case 'interval':
                return (0.95, 0.95)
            case _:
                raise ValueError(f'Unknown dsa_bounds_type {var.dsa_bounds_type}')

class TwoParamNumericScalarValuedDistribution(NumericScalarValuedDistribution):
    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if len(parameters) != 2 :
            raise TypeError(f'Two numeric parameters expected, got {len(parameters)}')
        
        for i, prm in enumerate(parameters):
            if isinstance(prm, str):
                raise TypeError(f'Parameters must be numeric, parameter{i} is {type(prm)}')
            if isinstance(prm, Sequence):
                if len(prm) > 1:
                    raise TypeError(f'Parameters must be scalar, is sequence of length {len(prm)}')
                if isinstance(prm[0], str) | isinstance(prm[0], Sequence):
                    raise TypeError(f'Binomial parameters must be numeric, trials is {type(prm[0])}')

class VectorValuedDistribution(Distribution):

    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> VectorParam:
        ...

    @classmethod
    def _apply_dsa_bound(
        cls,
        deterministic_value: VectorParam,
        bound_type: DSA_BOUNDS_TYPE,
        bound_value: VectorParam,
        transform: tuple[VARIABLE_TRANSFORM, ...]
    ) -> VectorParam:
        match bound_type:
            case 'relative':
                try:
                    bound_value = np.asarray(bound_value, dtype = np.float64)
                except TypeError:
                    raise TypeError(f'bound_value must be numeric for relative bound_type, is {type(bound_value)}')
                
                if np.all(bound_value == 1.):
                    return deterministic_value
                elif np.all(bound_value == 0.):
                    return np.zeros_like(deterministic_value)
                
                for val in deterministic_value:
                    if isinstance(val, str):
                        raise TypeError('Cannot apply a relative bound_value to a string value')
                
                out_val = np.asarray(deterministic_value)
                for i, trans in enumerate(transform):
                    if trans == 'ln':
                        out_val[i] = np.log(out_val[i])
                
                out_val *= bound_value

                for i, trans in enumerate(transform):
                    if trans == 'ln':
                        out_val[i] = np.exp(out_val[i])
                
                return out_val
            case 'offset':
                try:
                    bound_value = np.asarray(bound_value, dtype = np.float64)
                except TypeError:
                    raise TypeError(f'bound_value must be numeric for offset bound_type, is {type(bound_value)}')
                
                if np.all(bound_value == 0.):
                    return deterministic_value

                for val in deterministic_value:
                    if isinstance(val, str):
                        raise TypeError('Cannot apply an offset bound_value to a string value')
                
                out_val = np.asarray(deterministic_value)
                for i, trans in enumerate(transform):
                    if trans == 'ln':
                        out_val[i] = np.log(out_val[i])
                
                out_val += bound_value

                for i, trans in enumerate(transform):
                    if trans == 'ln':
                        out_val[i] = np.exp(out_val[i])
                
                return out_val
            case 'absolute':
                return bound_value
            case _:
                raise ValueError(f'Unknown bound_type: {bound_type}')

    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> VectorParam:
        if not isinstance(var, VectorVariable):
            raise TypeError(f'Expected VectorVariable, got {type(var)}')
        match bound:
            case 'central':
                return var.deterministic_value
            case 'lower':
                return cls._apply_dsa_bound(
                    var.deterministic_value,
                    var.dsa_bounds_type,
                    var.dsa_lower,
                    var.transform
                )
            case 'upper':
                return cls._apply_dsa_bound(
                    var.deterministic_value,
                    var.dsa_bounds_type,
                    var.dsa_upper,
                    var.transform
                )
            case _:
                raise ValueError(f'Unknown DSA bound: {bound}')
    
    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> VectorParam:
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[VectorParam, VectorParam]:
        ...

class NumericVectorValuedDistribution(VectorValuedDistribution):

    permitted_dsa_bounds = (
        'absolute',
        'relative',
        'offset',
        'interval'
    )

    @classmethod
    def interval_function(
        cls, 
        interval: float,
        var: NumericVectorVariable
    ) -> tuple[NumericVectorParam, NumericVectorParam]:
        """
        The bounds of a confidence interval around each parameter
        """
        return (var.deterministic_value, var.deterministic_value)

    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> NumericVectorParam:
        ...
    
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> NumericVectorParam:
        if var.dsa_bounds_type == 'interval':
            if not isinstance(var, NumericVectorVariable):
                raise TypeError(f'Expected NumericVectorVariable, got {type(var)}')
            
            match bound:
                case 'central':
                    return cast(NumericVectorParam, super().dsa_value(var, bound))
                case 'lower':
                    lbound, ubound = cls.interval_function(var.dsa_lower[0], var)
                    return lbound
                case 'upper':
                    lbound, ubound = cls.interval_function(var.dsa_upper[0], var)
                    return ubound
                case _:
                    raise ValueError(f'Unknown DSA bounds: {bound}')
        return cast(NumericVectorParam, super().dsa_value(var, bound))
    
    @classmethod
    @abstractmethod
    def psa_value(
        cls,
        var: Variable,
        rng: np.random.Generator
    ) -> NumericVectorParam:
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(
        cls, 
        var: Variable
    ) -> tuple[NumericVectorParam, NumericVectorParam]:
        ...

class _ConstantParameterisation(Parameterisation):
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[ScalarParam]:
        ...

    @classmethod
    @abstractmethod
    def partial_generator(
        cls,
        parameter: tuple[Param, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[Param, ...],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarParam], tuple[ScalarParam]]:
        ...


class ConstantParameterisationDefault(
    _ConstantParameterisation
):
    names = ('value', )
    types = ('scalar', )
    defaults = (1., )
    
    @classmethod
    def generator(cls, value: Param, *args, **kwargs) -> tuple[ScalarParam]:
        if len(args):
            raise TypeError('Constant variable can only accept single value - use constant_vector')
        if isinstance(value, str):
            return (value, )
        elif isinstance(value, Sequence):
            if len(value) > 1:
                raise ValueError('Constant variable can only accept single value - use constant_vector')
            return (value[0], )
        elif isinstance(value, np.ndarray):
            flat = value.flatten()
            if len(flat) > 1:
                raise ValueError('Constant variable can only accept single value - use constant_vector')
            return (flat[0], )
        else:
            return (value, )
    
    @override
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[ScalarParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[Param],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarParam], tuple[ScalarParam]]:
        # As there is only a single parameter, there is no difference between setting a single parameter and all
        raw_par = (parameter[0],)
        if not isinstance(raw_par[0], str) and (isinstance(raw_par[0], Sequence) or isinstance(raw_par[0], np.ndarray)):
            raise TypeError(f'parameter expected to be of scalar type, is {type(parameter)}')

        return raw_par, cls.generator(parameter[0])
        

class ConstantDistribution(ScalarValuedDistribution):
    distribution = 'constant'
    parameterisations = [
        ConstantParameterisationDefault(),
    ]
    dsa_possible = True
    psa_possible = False

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if not isinstance(var, ConstantVariable):
            raise TypeError(f'Expecting var as ConstantVariable, is {type(var)}')
        if len(parameters) > 1 or len(parameters) < 1:
            raise TypeError(f'ConstantDistribution expects single scalar parameter, got {len(parameters)}')
        
        p0 = parameters[0]

        if isinstance(p0, str):
            if not(var.transform[0] == 'identity'):
                raise TypeError('parameters must have identity transform if it is a string')
        elif isinstance(p0, Sequence):
            if len(p0) == 0:
                raise ValueError('No parameter provided')
            elif len(p0) > 1:
                raise ValueError('Too many parameters. For a constant vector, set the variable_type to "vector" and then use a "constant_vector" distribution')
            if isinstance(p0[0], str):
                if not (var.transform[0] == 'identity'):
                    raise ValueError('constant value must have identity transform if it is a string')

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarParam:
        if not isinstance(var, ConstantVariable):
            raise TypeError(f'Expecting var as ConstantVariable, is {type(var)}')
        
        match var.transform[0]:
            case 'identity':
                return var.parameters[0]
            case 'ln':
                try:
                    return np.exp(var.parameters[0])
                except TypeError:
                    raise TypeError(f'parameters[0] cannot have ln transform applied - is {type(var.parameters[0])}')
            case _:
                raise ValueError(f'Unknown transform: {var.transform[0]}')
    
    @classmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarParam:
        if not isinstance(var, ConstantVariable):
            raise TypeError(f'Expecting var as ConstantVariable, is {type(var)}')
        
        return var.deterministic_value
    
    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[ScalarParam, ScalarParam]:
        if not isinstance(var, ConstantVariable):
            raise TypeError(f'Expecting var as ConstantVariable, is {type(var)}')
        match var.dsa_bounds_type:
            case 'relative':
                return (1, 1)
            case 'offset':
                return (0, 0)
            case 'absolute':
                return (var.deterministic_value, var.deterministic_value)
            case _:
                raise ValueError(f'Unknown bounds_type: {var.dsa_bounds_type}')


class _BinomialParameterisation(TwoParamParameterisation):
    ...
    
class BinomialParameterisationDefault(
    _BinomialParameterisation
):
    names = ('probability', 'trials')
    types = ('scalar', 'scalar')
    defaults = (0.25, 1)

    @classmethod
    def generator(
        cls,
        probability: ScalarNumParam,
        trials: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (trials, probability)
    
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0 or parameter[0] > 1:
                        raise ValueError(f'first parameter must be a probability in [0, 1], is: {parameter[0]}')
                    pargs = list(current_params)
                    pargs[0] = parameter[0]
                    pargs = tuple(pargs)
                case 1:
                    if parameter[0] < 0 or int(parameter[0]) != parameter[0]:
                        raise ValueError(f'second parameter must be a positive integer number of trials, is: {parameter[0]}')
                    pargs = list(current_params)
                    pargs[1] = parameter[0]
                    pargs = tuple(pargs)
        
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]


class BinomialParameterisationExpected(
    _BinomialParameterisation
):
    names = ('mean', 'trials')
    types = ('scalar', 'scalar')
    defaults = (0.25, 1)

    @classmethod
    def generator(
        cls,
        mean: ScalarNumParam,
        trials: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        if trials == 0:
            if mean == 0:
                return (0, 0)
            else:
                raise ValueError('Number of trials cannot be zero with a non-zero mean')

        return (trials, mean / trials)
    
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter must be a positive expected number of successes, is {parameter[0]}')
                    if parameter[0] > current_params[1]:
                        if autoscale:
                            current_p = current_params[0] / current_params[1]
                            new_trials = int(round(parameter[0] / current_p))
                            pargs = (parameter[0], new_trials)
                        else:
                            raise ValueError(f'first parameter must be bounded by the number of trials ({current_params[1]}), is {parameter[0]}')
                    else:    
                        pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0 or int(parameter[0]) != parameter[0]:
                        raise ValueError(f'second parameter must be a positive integer number of trials, is: {parameter[0]}')
                    if parameter[0] < current_params[0]:
                        if autoscale:
                            current_p = current_params[0] / current_params[1]
                            new_expected = current_p * parameter[0]
                            pargs = (new_expected, parameter[0])
                        else:
                            raise ValueError(f'second parameter (trials) cannot be less than the expected number of successes: {current_params[0]}; is {parameter[0]}')
                    else:
                        pargs = (current_params[0], parameter[0])
        
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
def _binomial_interval_function(
    interval: float,
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Binomial requires two parameters, {len(parameters)} provided')
    from scipy.stats import binom
    return binom.interval(interval, parameters[0], parameters[1])

class BinomialDistribution(TwoParamNumericScalarValuedDistribution):
    distribution = 'binomial'
    parameterisations: Sequence[_BinomialParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        BinomialParameterisationDefault(),
        BinomialParameterisationExpected(),
    ]
    dsa_possible = True
    psa_possible = True
    interval_function = _binomial_interval_function

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        super().parameter_validation(var, *parameters)
        parameters = cast(tuple[ScalarNumParam, ScalarNumParam], parameters)
        
        if parameters[0] < 0:
            raise ValueError(f'Number of trials must be positive, is {parameters[0]}')
        if int(parameters[0]) != parameters[0]:
            raise ValueError(f'Number of trials must be an integer, is {parameters[0]}')
        
        if parameters[1] < 0 or parameters[1] > 1:
            raise ValueError(f'Binomial probability parameter must be in [0, 1], is {parameters[1]}')
    
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        super().value_validation(var, *values)

        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if not (int(val) == val):
            raise ValueError(f'Binomial value expected to be integer, is {val}')
    
    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        if var.transform[0] != 'identity':
            raise ValueError(f'Binomial distribution must provide values with identity transform, is {var.transform[0]}')
        return np.round(float(var.parameters[0]) * float(var.parameters[1]), 0) # NB - 0.5 rounds down
    
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        if var.transform[0] != 'identity':
            raise ValueError(f'Binomial distribution must provide values with identity transform, is {var.transform[0]}')
        return super().dsa_value(var, bound)
    
    @classmethod
    def psa_value(
        cls, 
        var: Variable,
        rng: np.random.Generator
    ) -> ScalarNumParam:
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        return rng.binomial(int(var.parameters[0]), float(var.parameters[1]))
    
    @classmethod
    def dsa_auto_values(
        cls, 
        var: Variable, 
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        rval = super().dsa_auto_values(var, interval)
        var = cast(TwoParamNumericScalarVariable, var)

        # Make sure that the bounds provide integer values
        match var.dsa_bounds_type:
            case 'relative':
                lbound = max(0, int(round(var.deterministic_value * rval[0])))
                ubound = min(int(var.parameters[0]), int(round(var.deterministic_value * rval[1])))
                return (lbound / var.deterministic_value, ubound / var.deterministic_value)
            case 'offset':
                lbound = max(0, int(round(var.deterministic_value + rval[0])))
                ubound = min(int(var.parameters[0]), int(round(var.deterministic_value + rval[1])))
                return (lbound - var.deterministic_value, ubound - var.deterministic_value)
            case 'absolute':
                lbound = max(0, int(round(rval[0])))
                ubound = min(int(var.parameters[0]), int(round(rval[1])))
                return (lbound, ubound)

        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        if var.dsa_bounds_type == 'relative':
            return (0.9, 1.1)
        
        from scipy.stats import binom
        lbound, ubound = binom.interval(interval, var.parameters[0], var.parameters[1])
        lbound = max(0, int(round(lbound)))
        ubound = min(int(var.parameters[0]), int(round(ubound)))
        
        match var.dsa_bounds_type:
            case 'offset':
                return (
                    lbound - var.deterministic_value, 
                    ubound - var.deterministic_value
                )
            case 'absolute':
                return (lbound, ubound)
            case _:
                raise ValueError(f'Unknown dsa_bounds_type: {var.dsa_bounds_type}')


class _NormalParameterisation(TwoParamParameterisation):
    ...

class NormalParameterisationDefault(
    _NormalParameterisation
):
    names = ('mean', 'sd')
    types = ('scalar', 'scalar')
    defaults = (0, 1)

    @classmethod
    def generator(
        cls,
        mean: ScalarNumParam,
        sd: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (mean, sd)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    # Just about any value of mean is acceptable
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (sd) must be positive; is {parameter[0]}')
                    # Just about any postive value of sd is acceptable
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'identity'
    
class LogNormalParameterisationDefault(
    _NormalParameterisation
):
    names = ('mu', 'sigma')
    types = ('scalar', 'scalar')
    defaults = (0, 1)

    @classmethod
    def generator(
        cls,
        mu: ScalarNumParam,
        sigma: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        if sigma < 0:
            raise ValueError(f'Sigma parameter must be positive, is {sigma}')
        return (mu, sigma)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    # Just about any value of mu is acceptable
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (sigma) must be positive; is {parameter[0]}')
                    # Just about any postive value of sd is acceptable
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
        
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'ln'

class LogNormalParameterisationExpected(
    _NormalParameterisation
):
    names = ('mean', 'sd')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls,
        mean: ScalarNumParam,
        sd: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        if sd == 0:
            return (np.log(mean), 0)
        if mean <= 0:
            raise ValueError('Lognormal requires mean > 0')
        sigma_squared = np.log((sd*sd) / (mean*mean) + 1)
        mu = np.log(mean) - 0.5 * sigma_squared
        return (mu, np.sqrt(sigma_squared))
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] <= 0:
                        raise ValueError(f'first parameter (mean) must be positive nonzero; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (sigma) must be positive; is {parameter[0]}')
                    # Just about any postive value of sd is acceptable
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'ln'
    
def _normal_interval(
    interval: float, 
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Normal requires two parameters, {len(parameters)} provided')
    from scipy.stats import norm
    return norm.interval(interval, parameters[0], parameters[1])

def _lognormal_interval(
    interval: float,
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Lognormal requires two parameters, {len(parameters)} provided')
    from scipy.stats import lognorm
    # NB - whilst stats.lognorm requires exponentiation of mu to get the scale,
    # random.lognorm does not. 
    return lognorm.interval(interval, parameters[1], scale=np.exp(parameters[0]))
    
class NormalDistribution(TwoParamNumericScalarValuedDistribution):
    distribution = 'normal'
    parameterisations: Sequence[_NormalParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        NormalParameterisationDefault(),
        LogNormalParameterisationDefault(),
        LogNormalParameterisationExpected(),
    ]

    dsa_possible = True
    psa_possible = True
    interval_function = _normal_interval

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        
        super().parameter_validation(var, *parameters)
        parameters = cast(tuple[ScalarNumParam, ScalarNumParam], parameters)

        if parameters[1] < 0:
            raise ValueError(f'Second parameter (sd/sigma) must be positive, is {parameters[1]}')

   # Value validation can be inherited from NumericScalarValuedDistribution

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        if var.transform[0] == 'ln':
            return np.exp(var.parameters[0] + 0.5 * var.parameters[1]**2)
        else:
            return var.parameters[0]
    
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        if var.transform[0] == 'ln' and var.dsa_bounds_type == 'interval':
            if not isinstance(var, NumericScalarVariable):
                raise TypeError(f'Expected NumericScalarVariable, got {type(var)}')

            interval_function = _lognormal_interval
            
            match bound:
                case 'central':
                    return cast(float, super().dsa_value(var, bound))
                case 'lower':
                    lbound, ubound = interval_function(float(var.dsa_lower), var.parameters)
                    return lbound
                case 'upper':
                    lbound, ubound = interval_function(float(var.dsa_upper), var.parameters)
                    return ubound
                case _:
                    raise ValueError(f'Unknown DSA bounds: {bound}')

        return super().dsa_value(var, bound)

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> ScalarNumParam:
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')

        if var.parameters[1] == 0:
            return var.deterministic_value
        
        if var.transform[0] == 'ln':
            return rng.lognormal(*var.parameters)
        return rng.normal(*var.parameters)

    @classmethod
    def dsa_auto_values(
        cls,
        var: Variable, 
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        match var.transform[0]:
            case 'identity':
                return super().dsa_auto_values(var, interval)
            case 'ln':
                if not isinstance(var, NumericScalarVariable):
                    raise TypeError(f'Expected var as NumericScalarVariable, got {type(var)}')
                interval_function = _lognormal_interval
                match var.dsa_bounds_type:
                    case 'relative':
                        return (0.9, 1.1)
                    case 'offset':
                        lbound, ubound = interval_function(interval, var.parameters)
                        return (lbound - var.deterministic_value, ubound - var.deterministic_value)
                    case 'absolute':
                        lbound, ubound = interval_function(interval, var.parameters)
                        return (lbound, ubound)
                    case _:
                        raise ValueError(f'Unknown dsa_bounds_type {var.dsa_bounds_type}')

class _BetaParameterisation(TwoParamParameterisation):
    ...

class BetaParameterisationDefault(
    _BetaParameterisation
):
    names = ('a', 'b')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls, 
        a: ScalarNumParam, 
        b: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (a, b)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter (a) must be positive; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (b) must be positive; is {parameter[0]}')
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'identity'

class BetaParameterisationExpected(
    _BetaParameterisation
):
    names = ('mean', 'sd')
    types = ('scalar', 'scalar')
    defaults = (0.5, 0.25)

    @classmethod
    def generator(
        cls, 
        mean: ScalarNumParam, 
        sd: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        if mean == 0:
            return (0, 1)
        elif mean == 1:
            return (1, 0)
        
        # Method of moments
        mom = ((mean * (1 - mean)) / (sd*sd) - 1)
        a = mean * mom
        b = (1.0 - mean) * mom
        return (a, b)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0 or parameter[0] > 1:
                        raise ValueError(f'first parameter (mean) must be in [0, 1]; is {parameter[0]}')
                    numer = parameter[0] * (1 - parameter[0])
                    denom = current_params[1] * current_params[1]
                    if (numer / denom) < 1:
                        if autoscale:
                            sd = np.sqrt(numer)
                            pargs = (parameter[0], sd)
                        else:
                            raise ValueError(f'mean ({parameter[0]}) incompatible with Beta sd ({current_params[1]})')
                    else:
                        pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0 or parameter[0] > 0.5:
                        raise ValueError(f'second parameter (sd) must be in [0, 0.5], is {parameter[0]}')
                    
                    numer = current_params[0] * (1 - current_params[0])
                    denom = parameter[0] * parameter[0]
                    if (numer / denom) < 1:
                        if autoscale:
                            is_left = current_params[0] < 0.5
                            numer = denom
                            mean_ = (1. + np.sqrt(1. - 4. * numer)) / 2.
                            if is_left:
                                pargs = (1-mean_, parameter[0])
                            else:
                                pargs = (mean_, parameter[0])
                        else:
                            raise ValueError(f'second parameter (sd) incompatible with mean; mean = {current_params[0]}, sd attempted = {parameter[0]}')
                    else:
                        pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'identity'

class LogBetaParameterisationDefault(
    _BetaParameterisation
):
    names = ('a_log', 'b_log')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls, 
        a_log: ScalarNumParam, 
        b_log: ScalarNumParam, 
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (a_log, b_log)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter (a_log) must be positive; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (b_log) must be positive; is {parameter[0]}')
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'ln'

def _beta_interval(
    interval: float, 
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Beta requires two parameters, {len(parameters)} provided')
    from scipy.stats import beta
    return beta.interval(interval, parameters[0], parameters[1])

class BetaDistribution(TwoParamNumericScalarValuedDistribution):
    distribution = 'beta'
    parameterisations: Sequence[_BetaParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        BetaParameterisationDefault(),
        BetaParameterisationExpected(),
        LogBetaParameterisationDefault()
    ]

    dsa_possible = True
    psa_possible = True
    interval_function = _beta_interval

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        
        super().parameter_validation(var, *parameters)
        parameters = cast(tuple[ScalarNumParam, ScalarNumParam], parameters)
        
        if parameters[0] < 0:
            raise ValueError(f'First parameter (a) must be positive, is {parameters[0]}')
        if parameters[1] < 0:
            raise ValueError(f'Second parameter (b) must be positive, is {parameters[1]}')

    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        super().value_validation(var, *values)

        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if var.transform[0] != 'ln' and (val < 0 or val > 1):
            raise ValueError(f'Value expected in range [0, 1], is {val}')
        
    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        a, b = var.parameters
        if var.transform[0] == 'ln':
            from scipy.stats import beta
            return float(beta.expect(np.exp, (a,b)))
        else:
            return a / (a + b)
        
    # dsa_value can be inherited from NumericScalarValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> ScalarNumParam:
        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        
        a, b = var.parameters
        if a == 0 or b == 0:
            return var.deterministic_value

        v = rng.beta(a, b)
        
        if var.transform[0] == 'ln':
            return np.exp(v)
        return v


class _GammaParameterisation(TwoParamParameterisation):
    ...

class GammaParameterisationDefault(
    _GammaParameterisation
):
    names = ('shape', 'scale')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls, 
        shape: ScalarNumParam,
        scale: ScalarNumParam,
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (shape, scale)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter (shape) must be positive; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (scale) must be positive; is {parameter[0]}')
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'identity'
    
class GammaParameterisationExpected(
    _GammaParameterisation
):
    names = ('mean', 'sd')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls,
        mean: ScalarNumParam,
        sd: ScalarNumParam,
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        # Mean of gamma is:
        # mean = shape * scale
        # Variance of gamma is:
        # var = shape * scale**2
        # sd = sqrt(shape) * scale
        # So:
        # scale = mean/shape
        # sd = sqrt(shape) * mean / shape = mean / sqrt(shape)
        # shape = (mean / sd) **2
        if sd < 0:
            raise ValueError(f'sd must be positive, is: {sd}')
        if mean < 0:
            raise ValueError(f'Mean must be positive, is: {mean}')
        if mean == 0:
            return(0., 0.)
        if sd == 0:
            return(0, mean)
        shape = (mean / sd) ** 2
        scale = mean / shape
        return (shape, scale)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter (mean) must be positive; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (sd) must be positive; is {parameter[0]}')
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'identity'

class LogGammaParameterisationDefault(
    _GammaParameterisation
):
    names = ('shape_log', 'scale_log')
    types = ('scalar', 'scalar')
    defaults = (1, 1)

    @classmethod
    def generator(
        cls, 
        shape_log: ScalarNumParam,
        scale_log: ScalarNumParam,
        *args, **kwargs
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        return (shape_log, scale_log)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[ScalarNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[ScalarNumParam, ScalarNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[ScalarNumParam, ScalarNumParam], tuple[ScalarNumParam, ScalarNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    if parameter[0] < 0:
                        raise ValueError(f'first parameter (shape_log) must be positive; is {parameter[0]}')
                    pargs = (parameter[0], current_params[1])
                case 1:
                    if parameter[0] < 0:
                        raise ValueError(f'second parameter (scale_log) must be positive; is {parameter[0]}')
                    pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return var.transform[0] == 'ln'

def _gamma_interval(
    interval: float,
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Gamma requires two parameters, {len(parameters)} provided')
    from scipy.stats import gamma
    return gamma.interval(interval, a = parameters[0], scale = parameters[1])

# CAUTION! Scipy incorrectly refers to the exponential gamma as the loggamma.
def _loggamma_interval(
    interval: float,
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Log-Gamma requires two parameters, {len(parameters)} provided')
    #from scipy.stats import loggamma
    #return loggamma.interval(interval, c = parameters[0], scale = parameters[1])
    from scipy.stats import gamma
    interval_values = gamma.interval(interval, a = parameters[0], scale = parameters[1])
    return (np.exp(interval_values[0]), np.exp(interval_values[1]))

class GammaDistribution(TwoParamNumericScalarValuedDistribution):
    distribution = 'gamma'
    parameterisations: Sequence[_GammaParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        GammaParameterisationDefault(),
        GammaParameterisationExpected(),
        LogGammaParameterisationDefault()
    ]

    dsa_possible = True
    psa_possible = True
    interval_function = _gamma_interval

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        
        super().parameter_validation(var, *parameters)
        parameters = cast(tuple[ScalarNumParam, ScalarNumParam], parameters)
        
        if parameters[0] < 0:
            raise ValueError(f'First parameter (a) must be positive, is {parameters[0]}')
        if parameters[1] < 0:
            raise ValueError(f'Second parameter (b) must be positive, is {parameters[1]}')
        
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        super().value_validation(var, *values)

        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if var.transform[0] == 'identity' and val < 0 :
            raise ValueError(f'Value expected to be positive, is {val}')

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        shape, scale = var.parameters
        if var.transform[0] == 'ln':
            # Do not trust scipy loggamma - is actually exponential gamma
            import scipy.integrate as integrate
            from scipy.stats import gamma as gamma_dist
            
            return integrate.quad(lambda x: 1 - gamma_dist.cdf(np.log(x), a = shape, scale = scale), 0, np.inf)[0]
        else:
            if scale == 0:
                return 0.
            elif shape == 0:
                return scale
            return shape * scale
        
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        if var.transform[0] == 'ln' and var.dsa_bounds_type == 'interval':
            if not isinstance(var, NumericScalarVariable):
                raise TypeError(f'Expected NumericScalarVariable, got {type(var)}')

            interval_function = _loggamma_interval
            
            match bound:
                case 'central':
                    return cast(float, super().dsa_value(var, bound))
                case 'lower':
                    lbound, ubound = interval_function(float(var.dsa_lower), var.parameters)
                    return lbound
                case 'upper':
                    lbound, ubound = interval_function(float(var.dsa_upper), var.parameters)
                    return ubound
                case _:
                    raise ValueError(f'Unknown DSA bounds: {bound}')

        return super().dsa_value(var, bound)

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> ScalarNumParam:
        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        
        shape, scale = var.parameters
        
        v = rng.gamma(shape, scale)
        
        if var.transform[0] == 'ln':
            return np.exp(v)
        return v
    
    @classmethod
    def dsa_auto_values(
        cls,
        var: Variable, 
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        match var.transform[0]:
            case 'identity':
                return super().dsa_auto_values(var, interval)
            case 'ln':
                if not isinstance(var, NumericScalarVariable):
                    raise TypeError(f'Expected var as NumericScalarVariable, got {type(var)}')
                interval_function = _loggamma_interval
                match var.dsa_bounds_type:
                    case 'relative':
                        return (0.9, 1.1)
                    case 'offset':
                        lbound, ubound = interval_function(interval, var.parameters)
                        return (lbound - var.deterministic_value, ubound - var.deterministic_value)
                    case 'absolute':
                        lbound, ubound = interval_function(interval, var.parameters)
                        return (lbound, ubound)
                    case _:
                        raise ValueError(f'Unknown dsa_bounds_type {var.dsa_bounds_type}')


class _ConstantVectorParameterisation(VectorParameterisation):
    ...

class ConstantVectorParameterisationDefault(
    _ConstantVectorParameterisation
):
    names = ('values',)
    types = ('vector',)
    defaults = ([1], )

    @classmethod
    def generator(
        cls,
        values: VectorParam,
        *args, **kwargs
    ) -> tuple[VectorParam]:
        if len(args) > 0:
            # Assume that we need to concat
            if not isinstance(values, Sized):
                return ([values] + list(args),)
            elif isinstance(values, str):
                return ([values] + list(args),)
            else:
                # Was planning to unpack, but this feels more consistent if not type-safe
                return ([values] + list(args), ) # pyright: ignore[reportReturnType]
        if isinstance(values, str):
            return ([values], )
        elif isinstance(values, np.ndarray):
            return (values.flatten(), )
        elif not isinstance(values, Sequence):
            return ([values], )
        else:
            return (values, )
    
    @override
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[VectorParam],
        parameter_index: tuple[int, ...],
        current_params: tuple[VectorParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[VectorParam], tuple[VectorParam]]:
        # As there is only a single parameter, there is no difference between setting a single parameter and all
        return parameter, cls.generator(parameter[0])
    

class ConstantVectorDistribution(VectorValuedDistribution):
    distribution = 'constant_vector'
    parameterisations: Sequence[_ConstantVectorParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        ConstantVectorParameterisationDefault(),
    ]

    dsa_possible = True
    psa_possible = False

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if len(parameters) != 1:
            raise TypeError(f'Single parameter sequence expected, got {len(parameters)} separate parameters')
        
        # Happy with pretty much anything else, even a sequence of sequences.
    
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        if len(values) != 1:
            raise TypeError(f'Single vector or Sequence of values expected, got {len(values)} individual values')
        val = values[0]
        if (
            isinstance(val, str) 
            or not (
                isinstance(val, Sequence)
                or isinstance(val, np.ndarray)
            )
        ):      
            raise TypeError(f'Vector or sequence expected, got {type(val)}')
        
    @classmethod
    def deterministic_value(cls, var: Variable) -> VectorParam:
        if not isinstance(var, ConstantVectorVariable):
            raise TypeError(f'Expecting var as ConstantVectorVariable, is {type(var)}')
        rval = copy.copy(var.parameters[0])
        if (
            isinstance(rval, str)
            or not (
                isinstance(rval, Sequence)
                or isinstance(rval, np.ndarray)
            )
        ):
            rval = [rval]
        elif isinstance(rval, Sequence):
            rval = list(rval)
        elif isinstance(rval, np.ndarray):
            if not rval.dtype == np.float64:
                rval = rval.astype(np.float64)
            if len(rval.shape) > 1:
                rval = rval.flatten()
            else:
                rval = cast(np.ndarray[tuple[int], Any], rval)
        for i, trans in enumerate(var.transform):
            match trans:
                case 'ln':
                    try:
                        rval[i] = np.exp(rval[i])
                    except ValueError as e:
                        raise TypeError(f'value[{i}]')
        return rval
    
    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> VectorParam:
        if not isinstance(var, ConstantVectorVariable):
            raise TypeError(f'Expecting var as ConstantVectorVariable, is {type(var)}')
        return var.deterministic_value
    
    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[VectorParam, VectorParam]:
        if not isinstance(var, ConstantVectorVariable):
            raise TypeError(f'Expecting var as ConstantVectorVariable, is {type(var)}')
        match var.dsa_bounds_type:
            case 'relative':
                return (np.ones_like(var.parameters[0]), np.ones_like(var.parameters[0]))
            case 'offset':
                return (np.zeros_like(var.parameters[0]), np.zeros_like(var.parameters[0]))
            case 'absolute':
                return (var.deterministic_value, var.deterministic_value)
            case _:
                raise ValueError(f'Unknown bounds_type: {var.dsa_bounds_type}')
        

class _MultivariateNormalParameterisation(VectorParameterisation):
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[NumericVectorParam, MatrixNumParam]:
        ...

class MultivariateNormalParameterisationDefault(
    _MultivariateNormalParameterisation
):
    names = ('mean', 'vcv')
    types = ('vector', 'matrix')
    defaults = (np.asarray([0.,0.,]), np.asarray([[1., 0.],[0.,1.]]))

    @classmethod
    def generator(
        cls,
        mean: NumericVectorParam,
        vcv: MatrixNumParam, 
        *args, **kwargs
    ) -> tuple[NumericVectorParam, MatrixNumParam]:
        if not isinstance(mean, np.ndarray):
            mean = np.asarray(mean, dtype = np.float64)
        if not isinstance(vcv, np.ndarray):
            vcv = np.asarray(vcv, dtype = np.float64)
        mean = mean.flatten()
        n_means = len(mean)
        vcv = vcv.reshape((n_means, n_means))
        return (mean, vcv)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[NumericVectorParam | MatrixNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[NumericVectorParam, MatrixNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[NumericVectorParam, MatrixNumParam], tuple[NumericVectorParam, MatrixNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    # Just about any value of the mean vector is acceptable, so long as conformable with vcv
                    if len(parameter[0]) != current_params[1].shape[0]:
                        if autoscale:
                            if len(parameter[0]) < current_params[1].shape[0]:
                                pargs = (parameter[0], current_params[1][range(len(parameter[0])), range(len(parameter[0]))])
                            else:
                                prev_size = current_params[1].shape[0]
                                new_size = len(parameter[0])
                                vcv_ = np.zeros((new_size, new_size), dtype = np.float64)
                                for i in range(new_size):
                                    for j in range(new_size):
                                        if i < prev_size:
                                            if j < prev_size:
                                                vcv_[i,j] = current_params[1][i,j]
                                        else:
                                            if i == j:
                                                v  = parameter[0][i]
                                                if v > 1e-10:
                                                    vcv_[i,j] = (v * 0.2)**2 # Assumed 20% SD
                                                else:
                                                    vcv_[i,j] = (0.0001)
                                pargs = (parameter[0], vcv_)
                        else:
                            raise ValueError(f'first parameter (mean vector) of length {len(parameter[0])} not conformable with vcv matrix of shape {current_params[1].shape}')
                    else:
                        pargs = (parameter[0], current_params[1])
                case 1:
                    # Will accept any vcv so long as conformable with mean vector
                    new_vcv = np.asarray(parameter[0])
                    if len(current_params[0]) != new_vcv.shape[0]:
                        if autoscale:
                            if len(current_params[0]) < new_vcv.shape[0]:
                                new_means = np.zeros(new_vcv.shape[0], dtype=np.float64)
                                new_means[0:len(current_params[1])] = current_params[0]
                            else:
                                new_means = current_params[0][0:new_vcv.shape[0]]
                            pargs = (new_means, new_vcv)
                        else:
                            raise ValueError(f'second parameter (vcv matrix) of shape {new_vcv.shape} not conformable with mean vector of length {len(current_params[0])}')
                    else:
                        pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return all(trans == 'identity' for trans in var.transform)
    
class MultivariateLogNormalParameterisationDefault(
    _MultivariateNormalParameterisation
):
    names = ('mu', 'vcv')
    types = ('vector', 'matrix')
    defaults = (np.asarray([0.,0.,]), np.asarray([[1., 0.],[0.,1.]]))

    @classmethod
    def generator(
        cls,
        mu: NumericVectorParam,
        vcv: MatrixNumParam, 
        *args, **kwargs
    ) -> tuple[NumericVectorParam, MatrixNumParam]:
        if not isinstance(mu, np.ndarray):
            mu = np.asarray(mu, dtype = np.float64)
        if not isinstance(vcv, np.ndarray):
            vcv = np.asarray(vcv, dtype = np.float64)
        mu = mu.flatten()
        n_means = len(mu)
        vcv = vcv.reshape((n_means, n_means))
        return (mu, vcv)
    
    @classmethod
    def partial_generator(cls,
        parameter: tuple[NumericVectorParam | MatrixNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[NumericVectorParam, MatrixNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[NumericVectorParam, MatrixNumParam], tuple[NumericVectorParam, MatrixNumParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            # _multiparameter_partial_generation_broadcast has already ruled out any length of parameter_index other than 1
            match parameter_index[0]:
                case 0:
                    # Just about any value of the mean vector is acceptable, so long as conformable with vcv
                    if len(parameter[0]) != current_params[1].shape[0]:
                        if autoscale:
                            if len(parameter[0]) < current_params[1].shape[0]:
                                pargs = (parameter[0], current_params[1][range(len(parameter[0])), range(len(parameter[0]))])
                            else:
                                prev_size = current_params[1].shape[0]
                                new_size = len(parameter[0])
                                vcv_ = np.zeros((new_size, new_size), dtype = np.float64)
                                for i in range(new_size):
                                    for j in range(new_size):
                                        if i < prev_size:
                                            if j < prev_size:
                                                vcv_[i,j] = current_params[1][i,j]
                                        else:
                                            if i == j:
                                                v  = parameter[0][i]
                                                if v > 1e-10:
                                                    vcv_[i,j] = (v * 0.2)**2 # Assumed 20% SD
                                                else:
                                                    vcv_[i,j] = (0.0001)
                                pargs = (parameter[0], vcv_)
                        else:
                            raise ValueError(f'first parameter (mu vector) of length {len(parameter[0])} not conformable with vcv matrix of shape {current_params[1].shape}')
                    else:
                        pargs = (parameter[0], current_params[1])
                case 1:
                    # Will accept any vcv so long as conformable with mean vector
                    new_vcv = np.asarray(parameter[0])
                    if len(current_params[0]) != new_vcv.shape[0]:
                        if autoscale:
                            if len(current_params[0]) < new_vcv.shape[0]:
                                new_means = np.zeros(new_vcv.shape[0], dtype=np.float64)
                                new_means[0:len(current_params[1])] = current_params[0]
                            else:
                                new_means = current_params[0][0:new_vcv.shape[0]]
                            pargs = (new_means, new_vcv)
                        else:
                            raise ValueError(f'second parameter (vcv matrix) of shape {new_vcv.shape} not conformable with mu vector of length {len(current_params[0])}')
                    else:
                        pargs = (current_params[0], parameter[0])
            
        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
                    
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return any(trans == 'ln' for trans in var.transform)
    
class MultivariateLogNormalParameterisationExpected(
    _MultivariateNormalParameterisation
):
    names = ('mean', 'vcv', 'transform')
    types = ('vector', 'matrix', 'vector')
    defaults = (np.asarray([1.,1.,]), np.asarray([[1., 0.],[0.,1.]])) # NB - do not provide transform, so that it is passed from the Variable at parameter set time

    @classmethod
    def generator(
        cls, 
        mean: NumericVectorParam,
        vcv: MatrixNumParam,
        transform: VectorParam,
        *args, **kwargs
    ) -> tuple[NumericVectorParam, MatrixNumParam]:
        if not isinstance(mean, np.ndarray):
            mean = np.asarray(mean, dtype = np.float64)
        if not isinstance(vcv, np.ndarray):
            vcv = np.asarray(vcv, dtype = np.float64)
        mean = mean.flatten()
        n_means = len(mean)
        vcv = vcv.reshape((n_means, n_means))

        for i, trans in enumerate(transform):
            if trans == 'ln':
                sigma_squared = vcv[i,i]
                mean[i] = np.log(mean[i]) - 0.5 * sigma_squared
        
        return (mean, vcv)

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return any(trans == 'ln' for trans in var.transform)

class MultivariateNormalDistribution(NumericVectorValuedDistribution):
    distribution = 'mvn'
    parameterisations: Sequence[_MultivariateNormalParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        MultivariateNormalParameterisationDefault(),
        MultivariateLogNormalParameterisationDefault(),
        MultivariateLogNormalParameterisationExpected(),
    ]

    dsa_possible = True
    psa_possible = True

    @classmethod
    def interval_function(
        cls, 
        interval: float, 
        var: NumericVectorVariable
    ) -> tuple[NumericVectorParam, NumericVectorParam]:
        out_val = super().interval_function(interval, var)
        i = var.dsa_value_index
        if i >= len(out_val[0]):
            raise ValueError(f'Value selected for DSA ({i}) is out of bounds [0, {len(out_val)-1}]')

        var = cast(MultivariateNormalVariable, var)
        trans = var.transform[i]
        means, vcv = var.parameters
        match trans:
            case 'identity':
                lower, upper = _normal_interval(interval, (means[i], np.sqrt(vcv[i,i])))
            case 'ln':
                lower, upper = _lognormal_interval(interval, (means[i], np.sqrt(vcv[i,i])))
            case _:
                raise ValueError(f'Transform not recognised: {trans}')
            
        lower_vec = np.asarray(out_val[0])
        upper_vec = np.asarray(out_val[1])
        lower_vec[i] = lower
        upper_vec[i] = upper
        return (lower_vec, upper_vec)


    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if len(parameters) != 2:
            raise TypeError(f'Two parameters expected - vector of means and variance-covariance matrix; got {len(parameters)} separate parameters')
        
        if isinstance(parameters[0], np.ndarray):
            if len(parameters[0].shape) != 1:
                raise TypeError(f'Vector of means must be one dimensional, has {len(parameters[0].shape)} dimensions')
            n_means = len(parameters[0])
        elif isinstance(parameters[0], str):
            raise TypeError(f'Mean parameters must be numeric, scalar value is {type(parameters[0])}')
        elif isinstance(parameters[0], Sequence):
            for i, prm in enumerate(parameters[0]):
                if isinstance(prm, str) or isinstance(prm, Sequence):
                    raise TypeError(f'Mean parameters must be numeric, item {i} is {type(prm)}')
            n_means = len(parameters[0])
        else:
            n_means = 1
        
        if not isinstance(parameters[1], np.ndarray):
            raise TypeError(f'Variance-covariance matrix must be ndarray, is {type(parameters[1])}')
        if len(parameters[1].shape) != 2:
            raise TypeError(f'Variance-covariance matrix must be two dimensional, has shape {parameters[1].shape}')
        if not ((parameters[1].shape[0] == parameters[1].shape[1]) and parameters[1].shape[0] == n_means):
            raise TypeError(f'Matrix-covariance must be square of side {n_means}, has shape {parameters[1].shape}')

    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        if len(values) != 1:
            raise TypeError(f'Single vector or Sequence of values expected, got {len(values)} individual values')
        val = values[0]
        if (
            isinstance(val, str) 
            or not (
                isinstance(val, Sequence)
                or isinstance(val, np.ndarray)
            )
        ):      
            raise TypeError(f'Vector or sequence expected, got {type(val)}')
        
        if len(val) != var.n_values:
            raise TypeError(f'Expected vector of length {var.n_values}, got length {len(val)}')
        
        for i, item in enumerate(val):
            try:
                a = float(item)
            except ValueError:
                raise TypeError(f'Vector of numeric values expected, item {i} is {type(item)}')
            
    @classmethod
    def deterministic_value(cls, var: Variable) -> NumericVectorParam:
        if not isinstance(var, MultivariateNormalVariable):
            raise TypeError(f'Expecting var as MultivariateNormalVariable, is {type(var)}')
        var = cast(MultivariateNormalVariable, var)
        
        oarray = np.asarray(var.parameters[0]).flatten()
        vcv = var.parameters[1]


        for i, trans in enumerate(var.transform):
            if trans == 'ln':
                oarray[i] = np.exp(oarray[i] + 0.5 * vcv[i,i])
        return oarray
    
    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> NumericVectorParam:
        if not isinstance(var, MultivariateNormalVariable):
            raise TypeError(f'Expecting var as MultivariateNormalVariable, is {type(var)}')
        
        mean = np.asarray(var.parameters[0])
        vcv = np.asarray(var.parameters[1])
        oarray = rng.multivariate_normal(mean, vcv)
        for i, trans in enumerate(var.transform):
            if trans == 'ln':
                oarray[i] = np.exp(oarray[i])
        return oarray

    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[NumericVectorParam, NumericVectorParam]:
        if not isinstance(var, MultivariateNormalVariable):
            raise TypeError(f'Expecting var as MultivariateNormalVariable, is {type(var)}')
        match var.dsa_bounds_type:
            case 'relative':
                lower = np.zeros_like(var.parameters[0])
                upper = np.zeros_like(var.parameters[0])
                lower[var.dsa_value_index] = 0.9
                upper[var.dsa_value_index] = 1.1
                return (0.9 * np.ones_like(var.parameters[0]), 1.0 * np.ones_like(var.parameters[0]))
            case 'offset':
                lower, upper = cls.interval_function(0.95, var)
                det_val = np.asarray(var.deterministic_value)
                return (lower - det_val, upper - det_val)
            case 'absolute':
                lower, upper = cls.interval_function(0.95,var)
                return (lower, upper)
            case _:
                raise ValueError(f'Unknown bounds_type: {var.dsa_bounds_type}')

class _DirichletParameterisation(Parameterisation):
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[NumericVectorParam]:
        ...

class DirichletParameterisationDefault(
    _DirichletParameterisation
):
    names = ('alpha',)
    types = ('vector',)
    defaults = ([0.5, 0.5], )

    @classmethod
    def generator(
        cls,
        alpha: NumericVectorParam,
        *args, **kwargs
    ) -> tuple[NumericVectorParam, ]:
        alpha = np.asarray(alpha, dtype = np.float64).flatten()
        return (alpha, )
    
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[NumericVectorParam],
        parameter_index: tuple[int, ...],
        current_params: tuple[NumericVectorParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[NumericVectorParam], tuple[NumericVectorParam]]:
        # As there is only a single parameter, there is no difference between setting a single parameter and all
        return parameter, cls.generator(parameter[0]) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return all(trans == 'identity' for trans in var.transform)
    
class DirichletParameterisationExpected(
    _DirichletParameterisation
):
    names = ('mean', 'vcv')
    types = ('vector', 'matrix')
    # Note that the variance of values with equal concentration parameters must be the same
    defaults = (np.asarray([0.5, 0.5]), np.matrix([[0.25/3, -1/3], [-1/3, 0.25/3]]))

    @classmethod
    def generator(
        cls,
        mean: NumericVectorParam,
        vcv: MatrixNumParam,
        *args, **kwargs
    ) -> tuple[NumericVectorParam, ]:
        if not isinstance(mean, np.ndarray):
            mean = np.asarray(mean, dtype = np.float64)
        if not isinstance(vcv, np.ndarray):
            vcv = np.asarray(vcv, dtype = np.float64)
        mean = mean.flatten()
        meansum = np.sum(mean)
        if np.abs(meansum-1) > 1e-2:
            raise ValueError(f'Mean parameters do not sum to 1 (value = {meansum}). Dirichlet fitting will not be attempted.')
        elif np.abs(meansum-1) > 1e-16:
            warnings.warn(f'Mean parameters do not sum to 1 - sum is {meansum}. They will be standardised')
            mean = mean / meansum
        n_means = len(mean)
        vcv = vcv.reshape((n_means, n_means))

        alpha = fit_dirichlet(mean, vcv)
        checksum = np.sum(np.abs(mean - (alpha/np.sum(alpha))))
        if checksum > 1e-6:
            raise ArithmeticError(f'Dirichlet fitting unable to recover means - {alpha/np.sum(alpha)}.')

        return (alpha, )
    
    @classmethod
    def partial_generator(
        cls,
        parameter: tuple[NumericVectorParam | MatrixNumParam, ...],
        parameter_index: tuple[int, ...],
        current_params: tuple[NumericVectorParam, MatrixNumParam],
        *args,
        autoscale: bool = True,
        **kwargs
    ) -> tuple[tuple[NumericVectorParam, MatrixNumParam], tuple[NumericVectorParam]]:
        pargs = _multiparameter_partial_generation_broadcast(
            parameter, parameter_index, current_params
        )
        if pargs is None:
            match parameter_index[0]:
                case 0:
                    means_ = parameter[0]
                    if autoscale:
                        means_ = means_ / np.sum(means_)
                    if len(means_) != current_params[1].shape[0]:
                        if autoscale:
                            if len(parameter[0]) < current_params[1].shape[0]:
                                pargs = (parameter[0], current_params[1][range(len(parameter[0])), range(len(parameter[0]))])
                            else:
                                prev_size = current_params[1].shape[0]
                                new_size = len(parameter[0])
                                vcv_ = np.zeros((new_size, new_size), dtype = np.float64)
                                for i in range(new_size):
                                    for j in range(new_size):
                                        if i < prev_size:
                                            if j < prev_size:
                                                vcv_[i,j] = current_params[1][i,j]
                                        else:
                                            if i == j:
                                                v  = parameter[0][i]
                                                if v > 1e-10:
                                                    vcv_[i,j] = (v * 0.2)**2 # Assumed 20% SD
                                                else:
                                                    vcv_[i,j] = (0.0001)
                                pargs = (parameter[0], vcv_)
                        else:
                            raise ValueError(f'first parameter (mean vector) of length {len(parameter[0])} not conformable with vcv matrix of shape {current_params[1].shape}')
                    else:
                        pargs = (parameter[0], current_params[1])
                case 1:
                    # Will accept any vcv so long as conformable with mean vector
                    new_vcv = np.asarray(parameter[0])
                    if len(current_params[0]) != new_vcv.shape[0]:
                        if autoscale:
                            if len(current_params[0]) < new_vcv.shape[0]:
                                new_means = np.zeros(new_vcv.shape[0], dtype=np.float64)
                                new_means[0:len(current_params[1])] = current_params[0]
                            else:
                                new_means = current_params[0][0:new_vcv.shape[0]]
                            pargs = (new_means, new_vcv)
                        else:
                            raise ValueError(f'second parameter (vcv matrix) of shape {new_vcv.shape} not conformable with mean vector of length {len(current_params[0])}')
                    else:
                        pargs = (current_params[0], parameter[0])

        if pargs is None:
            raise ValueError(f'Unable to set parameters: {parameter}')
        
        return pargs, cls.generator(*pargs) # pyright: ignore[reportReturnType, reportArgumentType]

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        return all(trans == 'identity' for trans in var.transform)

class DirichletDistribution(NumericVectorValuedDistribution):
    distribution = 'dirichlet'
    parameterisations: Sequence[_DirichletParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        DirichletParameterisationDefault(),
        DirichletParameterisationExpected(),
    ]

    dsa_possible = True
    psa_possible = True

    @classmethod
    def interval_function(
        cls,
        interval: float,
        var: NumericVectorVariable
    ) -> tuple[NumericVectorParam, NumericVectorParam]:
        out_val = super().interval_function(interval, var)

        i = var.dsa_value_index
        if i >= len(out_val):
            raise ValueError(f'Value selected for DSA ({i}) is out of bounds [0, {len(out_val)-1}]')
        
        var = cast(DirichletVariable, var)

        a = var.parameters[0][i]
        b = np.sum(var.parameters[0]) - 1
        if a == 0 or b == 0:
            return out_val
        
        from scipy.stats import beta
        lower, upper = beta.interval(interval, a, b)
        
        det_vals = np.asarray(var.deterministic_value)
        value_prob = det_vals[i]
        resid_prob = 1. - value_prob
        
        # Lower
        scale_resid = (1. - lower) / resid_prob
        out_lower = copy.copy(det_vals)
        out_lower *= scale_resid
        out_lower[i] = lower
        out_lower /= np.sum(out_lower)

        # Upper
        scale_resid = (1. - upper) / resid_prob
        out_upper = copy.copy(det_vals)
        out_upper *= scale_resid
        out_upper[i] = upper
        out_upper /= np.sum(out_upper)

        return (out_lower, out_upper)
    
    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        if len(parameters) != 1:
            raise TypeError(f'Single numeric vector of concentration parameters expected - got {len(parameters)} individual parameters')
        
        prm = parameters[0]
        if isinstance(prm, np.ndarray):
            if len(prm.flatten()) < 2:
                raise TypeError(f'Dirichlet distribution requires at least two concentration parameters, {len(prm.flatten())} provided')
        elif isinstance(prm, Sequence):
            if len(prm) < 2:
                raise TypeError(f'Dirichlet distribution requires at least two concentration parameters, {len(prm)} provided')
        else:
            raise TypeError('Dirichlet requires a vector of at least two concentration parameters')
        
        for i, val in enumerate(prm):
            try:
                v = float(val)
            except ValueError:
                raise TypeError(f'Dirichlet concentration parameters must be numeric, parameter {i} has type {type(val)} ')

            if v < 0:
                raise ValueError(f'Dirichlet distribution requires positive concentration parameters, {i} is {v}')

    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        if len(values) != 1:
            raise TypeError(f'Single vector or Sequence of values expected, got {len(values)} individual values')
        val = values[0]
        if (
            isinstance(val, str) 
            or not (
                isinstance(val, Sequence)
                or isinstance(val, np.ndarray)
            )
        ):      
            raise TypeError(f'Vector or sequence expected, got {type(val)}')
        
        if len(val) != var.n_values:
            raise TypeError(f'Expected vector of length {var.n_values}, got length {len(val)}')

        for i, item in enumerate(val):
            try:
                a = float(item)
            except ValueError:
                raise TypeError(f'Vector of numeric values expected, item {i} is {type(item)}')
            
            if a < 0 or a > 1:
                raise ValueError(f'All values are expected within [0, 1], {i} is {a}')
        
        checksum = np.abs(np.sum(val) - 1)
        if checksum > 1e-12:
            raise ValueError(f'Dirichlet values should sum to 1, these sum to {np.sum(val)}')
        
    @classmethod
    def deterministic_value(cls, var: Variable) -> NumericVectorParam:
        if not isinstance(var, DirichletVariable):
            raise TypeError(f'Expecting var as DirichletVariable, is {type(var)}')
        var = cast(DirichletVariable, var)
        
        if any(trans == 'ln' for trans in var.transform):
            raise NotImplementedError('Log transform not implemented for Dirichlet distribution')

        oarray = np.asarray(var.parameters[0]).flatten()
        return oarray / np.sum(oarray)
    
    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> NumericVectorParam:
        if not isinstance(var, DirichletVariable):
            raise TypeError(f'Expecting var as DirichletVariable, is {type(var)}')
        if any(trans == 'ln' for trans in var.transform):
            raise ValueError('log transform not supported for Dirichlet')
        
        prm = np.array(var.parameters[0])
        if np.any(prm == 0):
            included = prm > 0
            oarray = np.zeros_like(prm)
            samp = rng.dirichlet(prm[included]).flatten()
            oarray[included] = samp
        else:
            oarray = rng.dirichlet(prm).flatten()
        return oarray
            
    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[NumericVectorParam, NumericVectorParam]:
        if not isinstance(var, DirichletVariable):
            raise TypeError(f'Expecting var as DirichletVariable, is {type(var)}')
        match var.dsa_bounds_type:
            case 'relative':
                lower = np.zeros_like(var.parameters[0])
                upper = np.zeros_like(var.parameters[0])
                lower[var.dsa_value_index] = 0.9
                upper[var.dsa_value_index] = 1.1
                return (0.9 * np.ones_like(var.parameters[0]), 1.0 * np.ones_like(var.parameters[0]))
            case 'offset':
                lower, upper = cls.interval_function(0.95, var)
                det_val = np.asarray(var.deterministic_value)
                return (lower - det_val, upper - det_val)
            case 'absolute':
                lower, upper = cls.interval_function(0.95,var)
                return (lower, upper)
            case _:
                raise ValueError(f'Unknown bounds_type: {var.dsa_bounds_type}')


@overload
def get_value_from_model(
    model: ModelType, 
    model_section: str | SequenceNotStr[str] | None, 
    model_parameter: str
) -> Value | Sequence[Value]:
    ...

@overload
def get_value_from_model(
    model: ModelType, 
    model_section: str | SequenceNotStr[str] | None, 
    model_parameter: SequenceNotStr[str]
) -> Sequence[Value]:
    ...

def get_value_from_model(
    model: ModelType, 
    model_section: str | SequenceNotStr[str] | None, 
    model_parameter: str | SequenceNotStr[str]
) -> Value | Sequence[Value]:
    if not isinstance(model_parameter, str) and isinstance(model_parameter, Sequence):
        if not isinstance(model_section, str) and isinstance(model_section, Sequence):
            if len(model_parameter) != len(model_section):
                if len(model_section) == 1:
                    return [
                        get_value_from_model(model, model_section[0], x) for x in model_parameter if (isinstance(x, str) or not isinstance(x, Sequence))
                    ] # pyright: ignore[reportReturnType]
                else:
                    raise TypeError(f'model_section length does not match model_parameter: {len(model_section)} vs {len(model_parameter)}')
            else:
                return [
                        get_value_from_model(model, x, y) for x, y in zip(model_section, model_parameter) if (isinstance(x, str) or not isinstance(x, Sequence))
                    ] # pyright: ignore[reportReturnType]
        else:
            return [
                get_value_from_model(model, model_section, x) for x in model_parameter if (isinstance(x, str) or not isinstance(x, Sequence))
            ] # pyright: ignore[reportReturnType]

    if model_section is not None and model_section != '':
        model_sec_chain = str(model_section).split('.')
        module = model
        for attr in model_sec_chain:
            try:
                module = getattr(module, attr)
            except AttributeError:
                if isinstance(module, Mapping):
                    try:
                        module = module[attr]
                    except AttributeError as e:
                        raise ValueError(f'Model section cannot be accessed: section {model_section} with error {e}')
    else:
        module = model

    model_param = str(model_parameter)

    try:
        model_val = getattr(module, model_param)
    except AttributeError:
        if isinstance(module, Mapping):
            model_val = module[model_param]
        else:
            raise ValueError(f'Model parameter cannot be accessed: {model_param}')
    return model_val

def update_model_with_value(
    value: Value,
    model: ModelType,
    model_section: str | None,
    model_parameter: str
) -> None:
    update_dict = {}
    last_dict = update_dict
    if model_section is not None and model_section != '':
        model_sec_chain = str(model_section).split('.')
        for key in model_sec_chain:
            last_dict[key] = {}
            last_dict = last_dict[key]
    
    last_dict[model_parameter] = value
    model.update(update_dict)


class Variable(
    newsegscomponent.NewsegsComponent
):
    """
    A single unit of variation in a model.

    May be associated with a single parameter, or a group of parameters that
    must co-vary (e.g. parameters for a statistical distribution, or a
    set of probabilities which form a simplex)
    """
    distribution: Distribution
    parameterisation_index: int

    configuration_show: bool = True
    """
    Create an input field on the model configuration page?
    """

    """
    Can variable participate in DSA?
    """
    dsa_selectable: bool = False
    """
    If possible, is variable selectable as candidate for DSA?
    """
    dsa_selected: bool = False
    """
    If possible and selectable, has variable been selected?
    """
    dsa_active: bool = False 
    """
    Has the variable been notified that the system is running a DSA?
    """
    dsa_focussed: bool = False
    """
    Has the variable been set as varying in the current run?
    """
    _dsa_show: bool = False
    """
    Create an input field on the dsa page?

    Variable must also be dsa_possible and dsa_selectable.
    """

    dsa_bounds_type: DSA_BOUNDS_TYPE = 'absolute'

    psa_selectable: bool = False
    """
    If possible, is variable selectable as part of PSA?
    """
    psa_selected: bool = False
    """
    If possible and selectable, has variable been selected for PSA?
    """
    psa_active: bool = False
    """
    Has the variable been notified that the system is running a PSA?
    """
    _psa_show: bool = False
    """
    Create an input field on the psa page?

    Variable must also be psa_possible and psa_selectable.
    """

    variable_type: VARIABLE_TYPE = 'scalar'
    _label: str | None = None

    # NewsegsComponent constants
    _id_prefix = 'v'
    # SerialiseToDictMixin constants
    _constructor_class = 'Variable'

    def __new__(
        cls,
        *args,
        distribution: VARIABLE_DISTRIBUTION = 'constant',
        **kwargs
    ):
        subclasses = {
            'constant': ConstantVariable,
            'binomial': BinomialVariable,
            'normal': NormalVariable,
            'beta': BetaVariable,
            'gamma': GammaVariable,
            'constant_vector': ConstantVectorVariable,
            'mvn': MultivariateNormalVariable,
            'dirichlet': DirichletVariable,
        }

        target_class = subclasses.get(distribution)

        if target_class is None:
            raise ValueError(f'Unknown distribution for Variable: {distribution}')
        
        return super().__new__(target_class)
    
    def __init__(
        self,
        name: str,
        label: str | None = None,
        unit: str = "",
        icon_name: str | SequenceNotStr[str] = "",
        configuration_type: CONFIGURATION_TYPE = 'model',
        model_section: str | SequenceNotStr[str] | None = None,
        model_parameter: str | SequenceNotStr[str] | None = None,
        interface_section: str | SequenceNotStr[str] | None = None,
        interface_key: str | SequenceNotStr[str] | None = None,
        interface_subindex: int = 0,
        distribution: VARIABLE_DISTRIBUTION = 'constant',
        transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM] = 'identity',
        parameterisation_index: int | None = None,
        parameters: ParamList | None = None,
        value_name: Sequence[str]| None = None,
        configuration_show: bool = True,
        dsa_show: bool = False,
        psa_show: bool = False,
        dsa_bounds_type: DSA_BOUNDS_TYPE = 'absolute',
        dsa_lower: Value | None = None,
        dsa_upper: Value | None = None,
        dsa_selectable: bool = False,
        dsa_selected: bool = False,
        dsa_active: bool = False,
        dsa_focussed: bool = False,
        psa_selectable: bool = False,
        psa_selected: bool = False,
        psa_active: bool = False,
        interface_min: float | None = None,
        interface_max: float | None = None,
        interface_step: float | None = None,
    ):
        super().__init__()
        self.name = name
    
        if label is not None:
            self.label = label

        self.unit = unit

        self.icon_name = icon_name

        self.configuration_type = configuration_type

        self.model_section = model_section
        if model_parameter:
            self.model_parameter = model_parameter
        else:
            self.model_parameter = self.name

        self.interface_section = interface_section
        if interface_key:
            self.interface_key = interface_key
        else:
            self.interface_key = self.name

        self.interface_subindex = interface_subindex

        # `distribution` will be absorbed by __new__
        #self.distribution = distribution

        self.set_distribution()
        if isinstance(transform, str) or not isinstance(transform, Sequence):
            self.set_transform(transform)
        else:
            self.set_transform(transform, autosize = False)
        if parameterisation_index is None:
            indexed_par = self.get_indexed_parameterisations()
            if len(indexed_par) > 0:
                parameterisation_index = int(indexed_par[0].get('index', 0))
            else:
                parameterisation_index = 0
        self.parameterisation_index = parameterisation_index
        self.dsa_bounds_type = dsa_bounds_type

        if parameters is None:
            self.set_default_parameters()
        else:
            if isinstance(parameters, str) or not isinstance(parameters, Sequence):
                self.set_parameters(parameters)
            else:
                self.set_parameters(*parameters)

        # If we have vector transformation, now we need to set it (again) to obey the number of values
        self.set_transform(transform)

        dsa_autovals = self.distribution.dsa_auto_values(self)

        if dsa_lower is None:
            self.dsa_lower = dsa_autovals[0]
        else:
            self.dsa_lower = dsa_lower
        
        if dsa_upper is None:
            self.dsa_upper = dsa_autovals[1]
        else:
            self.dsa_upper = dsa_upper

        self.dsa_selectable = dsa_selectable
        self.dsa_selected = dsa_selected
        self.dsa_active = dsa_active
        self.dsa_focussed = dsa_focussed
        self._dsa_show = dsa_show

        if value_name is None:
            self.value_name = [f'Value {i+1}' for i in range(self.n_values)]
        else:
            self.value_name = value_name

        self.psa_selectable = psa_selectable
        self.psa_selected = psa_selected
        self.psa_active = psa_active
        self._psa_show = psa_show

        self.configuration_show = configuration_show
        self.interface_min = interface_min
        self.interface_max = interface_max
        self.interface_step = interface_step

    @property
    def label(self) -> str:
        if self._label is None:
            return self.name
        return self._label
    
    @label.setter
    def label(self, label: str) -> None:
        self._label = label

    @property
    def parameterisation(self) -> Parameterisation:
        if self.parameterisation_index is None:
            raise AttributeError('No parameterisation index set')
        return self.distribution.parameterisations[self.parameterisation_index]

    @property
    @abstractmethod
    def parameters(self) -> tuple[ScalarParam | VectorParam | MatrixParam, ...]:
        ...
    
    def set_parameters(self, *parameters: Param):
        raw_parameters = copy.copy(parameters)
        
        native_params = self.distribution.parameterisations[self.parameterisation_index].generator(*parameters)
        self.distribution.parameter_validation(self, *native_params)

        self._raw_parameters = raw_parameters
        self._parameters = native_params

    def set_single_parameter(
        self,
        parameter_value: ScalarParam,
        parameter_index: int,
        parameter_vector_index: int = 0,
        autoscale = True
    ) -> tuple[bool, tuple[Param, ...]]:
        """
        Set a single indexed parameter and return whether setting was successful
        """
        try:
            raw_parameters, native_parameters = self.distribution.change_single_scalar_param(
                self, parameter_value, parameter_index, parameter_vector_index, autoscale
            )
            self._raw_parameters = raw_parameters
            self._parameters = native_parameters
        except (ValueError, TypeError):
            return False, self._raw_parameters
        return True, self._raw_parameters
    
    @property
    @abstractmethod
    def transform(self) -> tuple[VARIABLE_TRANSFORM, ...]:
        ...

    @abstractmethod
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        ...
    
    def get_deterministic_value(self) -> Value:
        v = self.distribution.deterministic_value(self)
        self.distribution.value_validation(self, v)
        return v

    @property
    def deterministic_value(self) -> Value:
        return self.get_deterministic_value()

    def set_distribution(self) -> None:
        pass

    @property
    def dsa_possible(self) -> bool:
        return self.distribution.dsa_possible
    
    @property
    def psa_possible(self) -> bool:
        return self.distribution.psa_possible
    
    @property
    def dsa_show(self) -> bool:
        """
        True if an input field should be created on the DSA page.

        NB - even if `.dsa_show` is set `True`, cannot return `True` if not 
        `.dsa_possible` or not `.dsa_selectable`
        """
        return self._dsa_show and self.dsa_possible and self.dsa_selectable
    
    @dsa_show.setter
    def dsa_show(self, show: bool) -> None:
        self._dsa_show = show

    @property
    def psa_show(self) -> bool:
        """
        True if an input field should be created on the PSA page.

        NB - even if `.psa_show` is set `True`, cannot return `True` if not 
        `.psa_possible` or not `.psa_selectable`
        """
        return self._psa_show and self.psa_possible and self.psa_selectable
    
    @psa_show.setter
    def psa_show(self, show: bool) -> None:
        self._psa_show = show
    
    def get_indexed_parameterisations(self):
        return [
            {'index':i, 'parameterisation': x} 
            for i, x in enumerate(self.distribution.parameterisations) 
            if x.eligibility(self)
        ]
    
    def find_parameterisation(self, filter: Callable[[Parameterisation], bool]) -> int:
        """
        Return the first available parameterisation to satisfy a filter.

        E.g. to find the first parameterisation that can take a "mean"
        parameter:
        
        var = Variable('name', distribution = 'normal', transform = 'ln')
        try:
            var.parameterisation_index = var.find_parameterisation(lambda x: 'mean' in x['names'])
        except ValueError as e:
            print(e)
        var.set_parameters(5, 2)
        """
        parameterisations = self.get_indexed_parameterisations()
        i = None
        for prm in parameterisations:
            if filter(prm['parameterisation']):
                i = prm['index']
                break
        if i is None:
            raise ValueError('Parameterisation not found')
        return i
    
    def set_default_parameters(self):
        parameterisation = self.distribution.parameterisations[self.parameterisation_index]
        defaults = parameterisation.defaults
        if isinstance(defaults, str) or not isinstance(defaults, Sequence):
            self.set_parameters(defaults)
        else:
            self.set_parameters(*defaults)

    @property
    def n_values(self) -> int:
        return self.distribution.n_values(self)
    
    @property
    def dsa_lower(self) -> Value:
        return self._dsa_lower
    
    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> Value:
        return self._dsa_upper
    
    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        self._dsa_upper = value
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> Value:
        """
        Get the deterministic sensitivity analysis value at the specified bound.

        Args:
            bound (DSA_BOUND): The sensitivity analysis bound to evaluate.
            force (bool, optional): If True, return the DSA value regardless of
                whether the parameter is currently selectable, selected, active,
                and focussed. Defaults to False.

        Returns:
            Param: The value of the parameter at the requested DSA bound, or the
                deterministic value if DSA is not available.
        """
        if self.distribution.dsa_possible:
            if (
                force
                or (
                    self.dsa_selectable
                    and self.dsa_selected
                    and self.dsa_active
                    and self.dsa_focussed
                )
            ):
                v = self.distribution.dsa_value(self, bound)
                self.distribution.value_validation(self, v)
                return v
        
        return self.deterministic_value
    
    def draw_psa(
        self,
        rng: np.random.Generator,
        retries: int = 1
        ) -> Param:
        if (
            self.distribution.psa_possible
            and self.psa_selectable
            and self.psa_selected
            and self.psa_active
        ):
            tries = 0
            while tries < retries:
                tries += 1
                v = self.distribution.psa_value(self, rng)
                ok = True
                try:
                    self.distribution.value_validation(self, v)
                except ValueError:
                    ok = False
                if ok:
                    self._psa_draw = v
                    return v
            warnings.warn(f'PSA draw failed for {self.name}')
            self._psa_draw = self.deterministic_value
        
        return self.deterministic_value
        
    def get_psa_value(self) -> Value:
        if (
            self.distribution.psa_possible
            and self.psa_selectable
            and self.psa_selected
            and self.psa_active
        ):
            return self._psa_draw
        return self.deterministic_value
    
    def is_model_type(self, model: ModelType) -> bool:
        match self.configuration_type:
            case 'model':
                return isinstance(model, NewsegsModelInterface)
            case 'finance':
                return isinstance(model, NewsegsFinanceInterface)
        return False
    
    def _update_model(self, model: ModelType, value: Value) -> None:
        if self.model_section is None or self.model_section == '':
            if not(isinstance(self.model_parameter, str)) and isinstance(self.model_parameter, Sequence):
                if isinstance(value, str) or not (isinstance(value, Sequence) or isinstance(value, np.ndarray)):
                    raise TypeError('Value expected to be of sequence type')
                for prm, val in zip(self.model_parameter, value):
                    update_model_with_value(val, model, None, model_parameter = prm)
            else:
                if isinstance(self.model_parameter, str):
                    update_model_with_value(value, model, None, self.model_parameter)
                elif isinstance(self.model_parameter, Sequence):
                    raise ValueError('Single model parameter expected')
                else:
                    update_model_with_value(value, model, None, self.model_parameter) # pyright: ignore[reportArgumentType]
        elif isinstance(self.model_section, str):
            if not(isinstance(self.model_parameter, str)) and isinstance(self.model_parameter, Sequence):
                if isinstance(value, str) or not (isinstance(value, Sequence) or isinstance(value, np.ndarray)):
                    raise TypeError('Value expected to be of sequence type')
                for prm, val in zip(self.model_parameter, value):
                    update_model_with_value(val, model, self.model_section, model_parameter = prm)
            else:
                if isinstance(self.model_parameter, str):
                    update_model_with_value(value, model, self.model_section, self.model_parameter)
                elif isinstance(self.model_parameter, Sequence):
                    raise ValueError('Single model parameter expected')
                else:
                    update_model_with_value(value, model, self.model_section, self.model_parameter) # pyright: ignore[reportArgumentType]
        elif isinstance(self.model_section, Sequence):
            if isinstance(value, str) or not (isinstance(value, Sequence) or isinstance(value, np.ndarray)):
                    raise TypeError('Value expected to be of sequence type')
            if not(isinstance(self.model_parameter, str)) and isinstance(self.model_parameter, Sequence):
                for val, prm, sec in zip(value, self.model_parameter, self.model_section):
                    update_model_with_value(val, model, sec, model_parameter = prm)
            else:
                if isinstance(self.model_parameter, str):
                    for val, sec in zip(value, self.model_section):
                        update_model_with_value(val, model, sec, self.model_parameter)

    
    def update_model(self, model: ModelType) -> None:
        self.update_model_deterministic(model)

    def update_model_deterministic(self, model: ModelType) -> None:
        """
        Set the associated parameter(s) in the model/finance to deterministic value(s).
        """
        if not self.is_model_type(model):
            return
        self._update_model(model, self.deterministic_value)

    def update_model_dsa(self, model: ModelType, bound: DSA_BOUND) -> None:
        if not self.is_model_type(model):
            return
        val = self.get_dsa_value(bound)
        self._update_model(model, val)

    def update_model_psa(self, model: ModelType) -> None:
        if not self.is_model_type(model):
            return
        val = self.get_psa_value()
        self._update_model(model, val)

    @abstractmethod
    def synchronise_from_model(self, model: ModelType) -> None:
        """
        Draw the appropriate value from the model and use it to set parameters.
        
        This is not a guaranteed operation; it may be that there is no 
        implementation of a parameterisation to go between the model value
        and the input parameters of the distribution, dependent upon the 
        transform. It is also likely that the variance parameters will be
        incorrect after synchronisation.

        It is therefore recommended that this operation be performed only in
        exceptional circumstances - it is better to store the raw parameters
        in the metamodel and update from that direction.
        """

    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        super().update(config)
        # Convert required attributes to tuple in case they have come from json
        if isinstance(config, dict):
            if '_raw_parameters' in config.keys():
                self._raw_parameters = tuple(self._raw_parameters)
            if '_parameters' in config.keys():
                self._parameters = tuple(self._parameters)
            if '_transform' in config.keys():
                self._transform = tuple(self._transform)

    def __deepcopy__(self, memo):
        o = Variable(self.name, distribution = self.distribution.distribution) # pyright: ignore[reportAbstractUsage]
        o.__dict__.update(copy.deepcopy(self.__dict__)) # pyright: ignore[reportAttributeAccessIssue]
        return o


class ScalarVariable(Variable):

    distribution: ScalarValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_lower: ScalarParam
    _dsa_upper: ScalarParam
    _transform: tuple[VARIABLE_TRANSFORM]

    model_parameter: str
    model_section: str | None
    interface_key: str
    interface_section: str | None    

    def _validate_bound(self, value: Value) -> ScalarParam:
        if not isinstance(value, str) and isinstance(value, Sequence):
            if len(value) != 1:
                raise TypeError(f'DSA bound should be a scalar value, got sequence of length {len(value)}')
            else:
                return value[0]
        elif isinstance(value, np.ndarray):
            if len(value.flatten()) != 1:
                raise TypeError(f'DSA bound should be a scalar value, got array of length {len(value.flatten())}')
            return value.flatten()[0]
        else:
            return value
        
    @property
    def dsa_lower(self) -> ScalarParam:
        return self._dsa_lower

    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> ScalarParam:
        return self._dsa_upper

    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_upper = value

    @property
    def transform(self) -> tuple[VARIABLE_TRANSFORM]:
        return self._transform
    
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        if isinstance(transform, str):
            if not transform in get_args(VARIABLE_TRANSFORM):
                raise ValueError(f'Transform not recognised: {transform}')
            self._transform = (transform,)
        elif isinstance(transform, Sequence):
            if len(transform) == 0:
                raise ValueError('Cannot set transform with no value')
            elif len(transform) > 1:
                raise ValueError(f'Too many transforms provided for scalar variable: {len(transform)}')
            if not transform[0] in get_args(VARIABLE_TRANSFORM):
                raise ValueError(f'Transform not recognised: {transform[0]}')
            self._transform =  cast(
                tuple[VARIABLE_TRANSFORM],
                tuple(transform[0])
            )
        else:
            raise ValueError(f'Transform type not recognised: {transform} of type {type(transform)}')
    
    @property
    def deterministic_value(self) -> ScalarParam:
        return cast(ScalarParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> ScalarParam:
        return cast(ScalarParam, super().get_dsa_value(bound, force))


class NumericScalarVariable(ScalarVariable):
    distribution: NumericScalarValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _parameters : tuple[ScalarNumParam, ...]

    @property
    def parameters(self) -> tuple[ScalarNumParam, ...]:
        return self._parameters

    @property
    def deterministic_value(self) -> ScalarNumParam:
        return cast(ScalarNumParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> ScalarNumParam:
        return cast(ScalarNumParam, super().get_dsa_value(bound, force))


class TwoParamNumericScalarVariable(NumericScalarVariable):
    distribution: TwoParamNumericScalarValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _parameters : tuple[ScalarNumParam, ScalarNumParam]

    @property
    def parameters(self) -> tuple[ScalarNumParam, ScalarNumParam]:
        return self._parameters

class VectorVariable(Variable):

    distribution: VectorValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_lower: VectorParam
    _dsa_upper: VectorParam
    _transform: tuple[VARIABLE_TRANSFORM, ...]

    variable_type = 'vector'

    def set_parameters(
        self, 
        *parameters: Param,
    ):
        super().set_parameters(*parameters)
        if len(self._parameters) == 0:
            return
        p1 = self._parameters[0]
        if not isinstance(p1, Sized):
            return
        if len(self.transform) > len(p1):
            self.set_transform(self.transform[0:len(p1)])
        elif len(self.transform) < len(p1):
            n_less = len(p1) - len(self.transform)
            tx = [self.transform[-1]]
            self.set_transform(list(self.transform) + tx * n_less)     # pyright: ignore[reportArgumentType]
            
    def _validate_bound(self, value: Value) -> VectorParam:
        if isinstance(value, str):
            return [value] * self.n_values
        elif isinstance(value, Sequence):
            if len(value) == 1:
                if self.n_values > 1:
                    return [*value] * self.n_values
            elif len(value) != self.n_values:
                raise TypeError(f'Incorrect number of dsa values: {self.n_values} expected, {len(value)} provided')
            return value
        elif isinstance(value, np.ndarray):
            value = value.flatten()
            if len(value) == 1:
                if self.n_values > 1:
                    return [*value] * self.n_values
            elif len(value) != self.n_values:
                raise TypeError(f'Incorrect number of dsa values: {self.n_values} expected, {len(value)} provided')
            return value
        else:
            return [value] * self.n_values
    
    @property
    def dsa_lower(self) -> VectorParam:
        return self._dsa_lower
    
    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> VectorParam:
        return self._dsa_upper
    
    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_upper = value
    
    @property
    def transform(self) -> tuple[VARIABLE_TRANSFORM, ...]:
        return self._transform
    
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        if isinstance(transform, str):
            if not transform in get_args(VARIABLE_TRANSFORM):
                raise ValueError(f'Transform not recognised: {transform}')
            if autosize:
                self._transform = (transform,) * self.n_values
            else:
                self._transform = (transform,)
        elif isinstance(transform, Sequence):
            if len(transform) == 0:
                raise ValueError('Cannot set transform with no value')
            elif len(transform) == 1:
                if not transform[0] in get_args(VARIABLE_TRANSFORM):
                    raise ValueError(f'Transform not recognised: {transform[0]}')
                if autosize:
                    self._transform = (transform[0],) * self.n_values
                else:
                    self._transform = (transform[0],)
            elif len(transform) != self.n_values and autosize:
                raise TypeError(f'Incorrect number of transforms: {self.n_values} expected, {len(transform)} provided')
            else:
                for i, trans in enumerate(transform):
                    if not trans in get_args(VARIABLE_TRANSFORM):
                        raise ValueError(f'Transform {i} not recognised: {trans}')
                transform = cast(Sequence[VARIABLE_TRANSFORM], transform)
                self._transform = cast(tuple[VARIABLE_TRANSFORM, ...], tuple(transform))
        else:
            raise ValueError(f'Transform type not recognised: {transform} of type {type(transform)}')
    
    @property
    def deterministic_value(self) -> VectorParam:
        return cast(VectorParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> VectorParam:
        return cast(VectorParam, super().get_dsa_value(bound, force))
    
    
class NumericVectorVariable(VectorVariable):
    distribution: NumericVectorValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_lower: NumericVectorParam # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_upper: NumericVectorParam # pyright: ignore[reportIncompatibleVariableOverride]

    dsa_value_index = 1
    """Which Value is of interest in DSA?"""

    @property
    def dsa_lower(self) -> NumericVectorParam:
        return self._dsa_lower
    
    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        if not (
            isinstance(value, Sequence)
            or isinstance(value, np.ndarray)
        ):
            raise TypeError(f'Expected a vector or sequence, got: {type(value)}')
        self._dsa_lower = cast(NumericVectorParam, value) # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def dsa_upper(self) -> NumericVectorParam:
        return self._dsa_upper
    
    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        if not (
            isinstance(value, Sequence)
            or isinstance(value, np.ndarray)
        ):
            raise TypeError(f'Expected a vector or sequence, got: {type(value)}')
        self._dsa_upper = cast(NumericVectorParam, value) # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    def deterministic_value(self) -> NumericVectorParam:
        return cast(NumericVectorParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> NumericVectorParam:
        return cast(NumericVectorParam, super().get_dsa_value(bound, force))


class ConstantVariable(ScalarVariable):
    distribution = ConstantDistribution()
    _parameters : tuple[ScalarParam]

    @property
    def parameters(self) -> tuple[ScalarParam]:
        return self._parameters
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        
        if model_val == self.deterministic_value:
            # No update
            return

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'value' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index
        
        if not isinstance(model_val, str) and isinstance(model_val, Sequence):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')
        
        self.set_parameters(model_val)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # As the constant distribution has only a single parameterisation, we should never get here
            raise NotImplementedError('Setting of raw parameters from alternative parameterisations not implemented for constant variables')

class BinomialVariable(TwoParamNumericScalarVariable):
    distribution = BinomialDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        
        if model_val == self.deterministic_value:
            # No update
            return

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        n_trials = self.parameters[1]
        
        if isinstance(model_val, str) or isinstance(model_val, Sequence):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')
        
        self.set_parameters(model_val, n_trials)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to probability, trial form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self._raw_parameters = copy.copy(self.parameters)


class NormalVariable(TwoParamNumericScalarVariable):
    distribution = NormalDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        if isinstance(model_val, str) or isinstance(model_val, Sequence):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')

        if self.transform[0] == 'identity':
            sd = self.parameters[1]
        else:
            sigma_squared = self.parameters[1]**2
            sd = np.sqrt((np.exp(sigma_squared) - 1) * (model_val * model_val))

        self.set_parameters(model_val, sd)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to mu, sigma form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self._raw_parameters = copy.copy(self.parameters)


class BetaVariable(TwoParamNumericScalarVariable):
    distribution = BetaDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return
        
        if isinstance(model_val, str) or isinstance(model_val, Sequence):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        if self.transform[0] == 'identity':
            a, b = self.parameters
            sd = np.sqrt(a*b / ((a+b)**2 * (a + b + 1.)))
            numer_ = model_val * (1 - model_val)
            denom_ = sd * sd
            if denom_ > numer_:
                sd = np.sqrt(0.9 * numer_)
        else:
            raise NotImplementedError('Derivation of log-beta parameters not supported')
        
        self.set_parameters(model_val, sd)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to a,b form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self._raw_parameters = copy.copy(self.parameters)


class GammaVariable(TwoParamNumericScalarVariable):
    distribution = GammaDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return
        
        if isinstance(model_val, str) or isinstance(model_val, Sequence):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        if self.transform[0] == 'identity':
            shape, scale = self.parameters
            sd = shape * scale**2
        else:
            raise NotImplementedError('Derivation of log-gamma parameters not supported')
        
        self.set_parameters(model_val, sd)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to shape, scale form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self._raw_parameters = copy.copy(self.parameters)


class ConstantVectorVariable(VectorVariable):
    distribution = ConstantVectorDistribution()
    _parameters: tuple[VectorParam] = ([1],)

    @property
    def parameters(self) -> tuple[VectorParam]:
        return self._parameters
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index
        
        self.set_parameters((model_val,)) # pyright: ignore[reportArgumentType]

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index


class MultivariateNormalVariable(NumericVectorVariable):
    distribution = MultivariateNormalDistribution()
    _parameters: tuple[NumericVectorParam, MatrixNumParam] = (np.asarray([0,0]), np.asarray([[1,0],[0,1]]))

    @property
    def parameters(self) -> tuple[NumericVectorParam, MatrixNumParam]:
        return self._parameters
    
    def set_parameters(self, *parameters: Param):
        if 'transform' in self.parameterisation.names and len(parameters) < 3:
            super().set_parameters(*parameters, self.transform)
        else:
            super().set_parameters(*parameters)

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return
        
        if not isinstance(model_val, np.ndarray):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')

        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'mean' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        if self.transform[0] == 'identity':
            sd = self.parameters[1]
        else:
            sigma_squared = self.parameters[1]**2
            sd = np.sqrt((np.exp(sigma_squared) - 1) * (model_val * model_val))
        
        self.set_parameters(model_val, sd)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to mu, vcv form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self._raw_parameters = copy.copy(self.parameters)


class DirichletVariable(NumericVectorVariable):
    distribution = DirichletDistribution()
    _parameters: tuple[NumericVectorParam] = (np.asarray([1,1]),)

    @property
    def parameters(self) -> tuple[NumericVectorParam]:
        return self._parameters
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        if not self.is_model_type(model):
            return
        
        model_val = get_value_from_model(model, self.model_section, self.model_parameter)
        if model_val == self.deterministic_value:
            # No update
            return
        
        if not isinstance(model_val, np.ndarray):
            raise TypeError(f'model_val cannot be synchronised to variable, is type {type(model_val)}')

        # NB - WE ARE NOT SETTING ON THE MEAN
        # Just going to set on the alphas and let the variance fall as it may.
        current_p_index = self.parameterisation_index
        try:
            new_p_index = self.find_parameterisation(lambda x: 'alpha' in x.names)
        except ValueError:
            raise ValueError(f'Cannot synchronise parameter {self.name} from model - no mean parameterisation')

        if not (current_p_index == new_p_index):
            self.parameterisation_index = new_p_index

        if self.transform[0] == 'identity':
            new_params = model_val
        else:
            raise NotImplementedError('Derivation of log-dirichlet parameters not supported')
        
        self.set_parameters(new_params)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            #TODO: Write back the means and VCV to the _raw_parameters
            # It is fairly trivial to write the VCV matrix, but just needs to be done,
            # especially considering we are messing with the matrix.

VARIABLE_CONSTRUCTORS = {
    'ConstantVariable': partial(Variable, distribution = 'constant'),
    'BinomialVariable': partial(Variable, distribution = 'binomial'),
    'NormalVariable': partial(Variable, distribution = 'normal'),
    'BetaVariable': partial(Variable, distribution = 'beta'),
    'GammaVariable': partial(Variable, distribution = 'gamma'),
    'ConstantVectorVariable': partial(Variable, distribution = 'constant_vector'),
    'MultivariateNormalVariable': partial(Variable, distribution = 'mvn'),
    'DirichletVariable': partial(Variable, distribution = 'dirichlet'),
}

def variable_from_dict(config: dict[str, Any]) -> Variable:
    classname = config.get('class')
    if classname is None:
        raise ValueError(f'`class` not found in configuration dictionary with keys {config.keys()}')
    constructor = VARIABLE_CONSTRUCTORS.get(classname)
    if constructor is None:
        raise ValueError(f'Constructor not found for {classname}')
    var = constructor('Placeholder')
    var.update(config)
    return var

def variable_uid(variable: Variable) -> str | list[str]:
    if not isinstance(variable.interface_key, str) and isinstance(variable.interface_key, Sequence):
        if isinstance(variable.interface_section, str):
            return list([lambda x: str(variable.interface_section) + "." + str(x) + "." + str(variable.interface_subindex) for x in variable.interface_key])
        else:
            return list([lambda x,y: str(y) + "." + str(x) + "." + str(variable.interface_subindex) for x,y in zip(variable.interface_key, variable.interface_section)])
    else:
        return str(variable.interface_section) + "." + str(variable.interface_key) + "." + str(variable.interface_subindex)
