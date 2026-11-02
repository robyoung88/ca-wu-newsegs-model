"""Variables: the statistical characterisation of the parameters of an energy or finance model.

A [`Variable`][newsegsmodelframework.newsegsvariable.variable.Variable] supplies the value, or
values, of one parameter (or of a group of parameters that must vary together) of a NewSEGS energy model or
finance model. It holds:

- **A distribution** that describes the uncertainty in the value: constant, binomial, normal,
  beta, gamma, constant vector, multivariate normal or Dirichlet.
- **Meta-parameters** that describe the distribution (e.g. the mean and standard deviation of
  a normal distribution). The same distribution may be *parameterised* in different ways (e.g. a
  log-normal by `mu` and `sigma` of the logarithm, or by the `mean` and `sd` of the value). The
  *raw* parameters, as the user gave them in the parameterisation, are stored with the
  variable and are converted to the *native* parameters of the distribution.
- **A transform** (`identity` or `ln`) that gives the model value as a function of the underlying
  distribution; `ln` makes the model value the exponential of the distribution, as for a
  log-normal or multivariate log-normal variable.
- **A deterministic (central) value**, derived from the distribution, which is used in an
  ordinary model run.
- **Bounds for one-way (deterministic) sensitivity analysis, DSA**: the lower and upper bounds
  of the value, specified as `absolute`, `offset`, `relative` or `interval` bounds.
- **Control information**: whether the variable may be, and is, selected for DSA, probabilistic
  sensitivity analysis (PSA) and optimisation, and whether it is shown on the corresponding pages.
- **Formatting information**: a label, unit, icon, default numeric format and the limits and step
  of the input field.
- **Location information**: the section and key under which it appears in the interface
  (`interface_section`, `interface_key`, `interface_subindex`, which together form the *varid*)
  and the section and parameter in the model that it sets (`model_section`, `model_parameter`).

The module is organised in three layers:

| Layer | Classes | Role |
|---|---|---|
| Parameterisation | `Parameterisation` and its subclasses | Convert the raw parameters a user gives into the native parameters of a distribution, and update them one at a time. |
| Distribution | `Distribution` and its subclasses | Statistical behaviour: validation, central value, standard deviation, intervals, DSA bounds and PSA draws. Stateless singletons. |
| Variable | `Variable` and its subclasses | The stateful component: holds the parameters and control information and updates the model. |

`Variable(name, distribution = ...)` returns an instance of the subclass for the distribution:

| `distribution` | Class | Parameterisations (raw parameters) |
|---|---|---|
| `constant` | `ConstantVariable` | `value` |
| `numeric_constant` | `NumericConstantVariable` | `value` |
| `binomial` | `BinomialVariable` | (`probability`, `trials`); (`mean`, `trials`) |
| `normal` | `NormalVariable` | (`mean`, `sd`); with `ln`: (`mu`, `sigma`); (`mean`, `sd`) of the log-normal |
| `beta` | `BetaVariable` | (`a`, `b`); (`mean`, `sd`); with `ln`: (`a_log`, `b_log`) |
| `gamma` | `GammaVariable` | (`shape`, `scale`); (`mean`, `sd`); with `ln`: (`shape_log`, `scale_log`) |
| `constant_vector` | `ConstantVectorVariable` | `values` |
| `mvn` | `MultivariateNormalVariable` | (`mean`, `vcv`); with `ln`: (`mu`, `vcv`); (`mean`, `vcv`, `transform`) |
| `dirichlet` | `DirichletVariable` | `alpha`; (`mean`, `vcv`) |

Example:
    ```python
    var = Variable(
        'capital_cost', distribution = 'normal', transform = 'ln',
        model_section = 'costs', model_parameter = 'capital',
        unit = 'GBP',
    )
    # The first parameterisation eligible for `ln` is (mu, sigma) of the logarithm;
    # choose the one which takes the mean and sd of the value itself.
    var.parameterisation_index = var.find_parameterisation(lambda p: 'mean' in p.names)
    var.set_parameters(1000., 150.)   # mean and sd of the log-normal value
    var.deterministic_value           # 1000.0
    var.update_model(finance)         # set finance.costs.capital
    ```

"""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
import copy
from functools import partial
import json
from typing import Any, Iterable, cast, Callable, Literal, Sequence, Sized, get_args, Union, overload, override
import warnings

from matplotlib.pylab import Generator
import numpy as np
import numpy.typing as npt
from useful_types import SequenceNotStr
from scipy.stats import gamma

from newsegsmodelframework.constants.framework_constants import COMPONENT_PREFIXES
from newsegsmodelframework.core import serialisation
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core import NewsegsComponent
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass
from newsegsmodelframework.newsegsstats.dirichlet import fit_dirichlet
from newsegsmodelframework.util import jsonfuncs

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
"""Whether a variable has a single value (`scalar`) or several (`vector`).
"""

PARAMETER_TYPE = Literal[
    'scalar',
    'vector',
    'matrix',
]
"""The type of a raw parameter of a distribution.
"""

VARIABLE_DISTRIBUTION = Literal[
    'constant',
    'numeric_constant',
    'binomial', # i.e. 0/1 for N trials (use 1 trial for bernoulli)
    'normal',
    'beta',
    'gamma',
    'constant_vector',
    'mvn', # multivariate normal
    'dirichlet', # for simplex i.e. vector of probabilities summing to 1
]
"""The distributions available to a variable.
"""

SCALAR_DISTRIBUTIONS = [
    'constant',
    'numeric_constant',
    'binomial',
    'normal',
    'beta',
    'gamma'
]
"""The distributions of scalar variables.
"""

VECTOR_DISTRIBUTIONS = [
    'constant_vector',
    'mvn',
    'dirichlet'
]
"""The distributions of vector variables.
"""

VARIABLE_TRANSFORM = Literal[
    'identity',
    'ln'
]
"""Transform from the underlying distribution to the model value: `identity`, or `ln` when the value is the exponential of the distribution.
"""

CONFIGURATION_TYPE = Literal[
    'model',
    'finance'
]
"""The kind of component whose parameter a variable sets: the energy `model` or the `finance` model.
"""

DSA_BOUND = Literal[
    'central',
    'lower',
    'upper'
]
"""The bounds of deterministic sensitivity analysis.
"""

DSA_BOUNDS_TYPE = Literal[
    'absolute',
    'offset',
    'relative',
    'interval'
]
"""How the DSA bounds are specified: an `absolute` value; an `offset` from, or `relative` multiple of, the central value; or the lower/upper limits of a confidence `interval`.
"""

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
    """Metaclass that creates a single instance of each class.

    The parameterisation and distribution classes have no instance state, so one instance of each is shared.
    """
    _instances = {}
    def __call__(cls, *args: Any, **kwargs: Any) -> Singleton:
        if cls not in cls._instances:
            cls._instances[cls] = (
                super(Singleton, cls)
                .__call__(*args, **kwargs)
            )
        return cls._instances[cls]

class Parameterisation(metaclass = Singleton):
    """A single way of parameterising a distribution.

    A distribution may be described by different sets of meta-parameters - for example a normal
    distribution by `mean` and `sd`, or a log-normal distribution by the `mu` and `sigma` of its
    logarithm or by the `mean` and `sd` of its value. Each is a `Parameterisation`: it knows the
    names, types and default values of the *raw* parameters, converts them into the *native*
    parameters of the distribution (`generator`), updates them one at a time (`partial_generator`)
    and says whether it can be used with the transform of a variable (`eligibility`).

    Attributes:
        names: Names of the raw parameters.
        types: Type of each raw parameter: `scalar`, `vector` or `matrix`.
        defaults: Default values of the raw parameters.
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
        """Whether the parameterisation can be used for a variable.

        Depends on the transform of the variable, e.g. a `LogNormalParameterisationDefault` is for variables with an `ln` transform. The default is always eligible.

        Args:
            var: The variable.

        Returns:
            True if the parameterisation can be used.
        """
        return True
    

class TwoParamParameterisation(Parameterisation):
    
    """Parameterisation of a distribution with two scalar numeric parameters.
    """
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Used when the user changes one parameter of a variable. The other parameters are adjusted (if `autoscale`) so that the set remains valid.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        ...

class VectorParameterisation(Parameterisation):

    """Parameterisation of a distribution with vector or matrix parameters.
    """
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[VectorParam|MatrixNumParam, ...]:
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Used when the user changes one parameter of a variable. The other parameters are adjusted (if `autoscale`) so that the set remains valid.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        ...
        
class Distribution(metaclass = Singleton):
    """Statistical behaviour of a type of variable.

    A distribution is a stateless singleton: it holds the list of its parameterisations and
    what it supports, and its methods take the variable whose parameters are to be used. It can
    say whether the variable's value can be varied in DSA, PSA and optimisation, validate
    parameters and values, and calculate the deterministic value, standard deviation and
    intervals, DSA bounds and PSA draws.

    Attributes:
        distribution: Name of the distribution (`VARIABLE_DISTRIBUTION`).
        parameterisations: The parameterisations that the distribution supports.
        dsa_possible: Whether the value can be varied in deterministic sensitivity analysis.
        psa_possible: Whether the value can be drawn in probabilistic sensitivity analysis.
        optim_possible: Whether the value can be varied in optimisation.
        permitted_dsa_bounds: The kinds of DSA bound that can be used.
    """
    distribution : VARIABLE_DISTRIBUTION
    parameterisations: Sequence[Parameterisation]
    dsa_possible: bool = False
    psa_possible: bool = False
    optim_possible: bool = False
    permitted_dsa_bounds: tuple[DSA_BOUNDS_TYPE,...] = (
        'absolute',
        'relative',
        'offset'
    )

    @classmethod
    def n_values(cls, var: Variable) -> int:
        """Number of values the variable provides.

        Args:
            var: The variable.

        Returns:
            The number of values: 1 for a scalar variable.
        """
        try:
            if (
                isinstance(var.parameters, str) 
                or not isinstance(var.parameters, Sequence)
            ):
                return 1
            p0 = var.parameters[0]
            if isinstance(p0, str) or not isinstance(p0, Sized):
                return 1
            return len(p0)
        except AttributeError:
            pass
        try:
            if (
                isinstance(var.raw_parameters, str) 
                or not isinstance(var.raw_parameters, Sequence)
            ):
                return 1
            p0 = var.raw_parameters[0]
            if isinstance(p0, str) or not isinstance(p0, Sized):
                return 1
            return len(p0)
        except AttributeError:
            return 1

    @classmethod
    @abstractmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
        ...
    
    @classmethod
    @abstractmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
        ...
    
    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> Value:
        """The central (deterministic) value of the variable.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        ...

    @classmethod
    @abstractmethod
    def std(cls, var: Variable) -> Value:
        """The standard deviation of the value.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        ...

    @classmethod
    @abstractmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[Value, Value]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        ...

    @classmethod
    @abstractmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> Value:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
        ...
    
    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> Value:
        """Draw a value for probabilistic sensitivity analysis.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[Value, Value]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
        current_params = var.raw_parameters
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
    """A distribution of a single value of any type, which may be a string.
    """
    @classmethod
    def n_values(cls, var: Variable) -> int:
        """Number of values the variable provides.

        Args:
            var: The variable.

        Returns:
            The number of values: 1 for a scalar variable.
        """
        return 1
    
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
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
        """The central (deterministic) value of the variable.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        ...

    @classmethod
    @abstractmethod
    def std(cls, var: Variable) -> ScalarParam:
        """The standard deviation of the value.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        ...

    @classmethod
    @abstractmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[ScalarParam, ScalarParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
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
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
        """Draw a value for probabilistic sensitivity analysis.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[ScalarParam, ScalarParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
        ...


class NumericScalarValuedDistribution(ScalarValuedDistribution):
    """A distribution of a single numeric value.

    Adds the `interval` DSA bound - the central interval of the distribution of the given probability - and the ability to be varied in optimisation.

    Attributes:
        interval_function: Function of a probability and the native parameters returning the lower and upper bounds of the central interval.
    """
    interval_function: Callable[[float, Sequence[ScalarNumParam]], tuple[float, float]]
    permitted_dsa_bounds = (
        'absolute',
        'relative',
        'offset',
        'interval'
    )
    optim_possible = True

    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
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
        """The central (deterministic) value of the variable.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        ...

    @classmethod
    @abstractmethod
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        ...

    @classmethod
    @abstractmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        if not isinstance(var, NumericScalarVariable):
            raise TypeError(f'var is expected to be NumericScalarVariable, is {type(var)}')
        v = cls.interval_function(confidence, var.parameters)
        if var.transform[0] == 'ln':
            v = tuple(np.exp(x) for x in v)
        return v

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
    
    @override
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
                    raise ValueError(f'Unknown DSA bounds: {bound} for variable {var.name} of type {type(var)}')
            
        return cast(float, super().dsa_value(var, bound))
    
    @classmethod
    @abstractmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarNumParam:
        """Draw a value for probabilistic sensitivity analysis.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        ...
    
    @classmethod
    def dsa_auto_values(
        cls, 
        var: Variable,
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.
            interval: Probability mass within the interval (e.g. 0.95).

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
    """A distribution of a single numeric value described by two numeric scalar parameters.
    """
    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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

    """A distribution of a vector of values, which may be of any type.
    """
    @classmethod
    @abstractmethod
    def deterministic_value(cls, var: Variable) -> VectorParam:
        """The central (deterministic) value of the variable.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        ...
    
    @classmethod
    @abstractmethod
    def std(cls, var: Variable) -> VectorParam:
        """The standard deviation of the value.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        ...

    @classmethod
    @abstractmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[VectorParam, VectorParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
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
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
        """Draw a value for probabilistic sensitivity analysis.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[VectorParam, VectorParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
        ...

class NumericVectorValuedDistribution(VectorValuedDistribution):

    """A distribution of a vector of numeric values.

    DSA varies the element at `dsa_value_index` of the variable. Allows the `interval` DSA bound.
    """
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
        """The central (deterministic) value of the variable.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        ...
    
    @classmethod
    @abstractmethod
    def std(cls, var: Variable) -> VectorParam:
        """The standard deviation of the value.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        ...

    @classmethod
    @abstractmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[VectorParam, VectorParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        if not isinstance(var, NumericVectorVariable):
            raise TypeError(f'var should be a NumericVectorVariable, is {type(var)}')
        return cls.interval_function(confidence, var)

    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> NumericVectorParam:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
        """Draw a value for probabilistic sensitivity analysis.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        ...
    
    @classmethod
    @abstractmethod
    def dsa_auto_values(
        cls, 
        var: Variable
    ) -> tuple[NumericVectorParam, NumericVectorParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
        ...

class _ConstantParameterisation(Parameterisation):
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[ScalarParam]:
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Used when the user changes one parameter of a variable. The other parameters are adjusted (if `autoscale`) so that the set remains valid.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        ...


class ConstantParameterisationDefault(
    _ConstantParameterisation
):
    """Parameterisation of the constant distribution by its `value`.

    Raw parameter: `value` - a single value of any type, including a string.

    Native parameter: `(value,)`.

    Eligible when always.
    """
    names = ('value', )
    types = ('scalar', )
    defaults = (1., )
    
    @classmethod
    def generator(cls, value: Param, *args, **kwargs) -> tuple[ScalarParam]:
        """Convert the raw parameters to the native parameters.

        Raw parameter: `value` - a single value of any type, including a string.

        Native parameter: `(value,)`.

        Args:
            value: The value.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameter: `value` - a single value of any type, including a string.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        raw_par = (parameter[0],)
        if not isinstance(raw_par[0], str) and (isinstance(raw_par[0], Sequence) or isinstance(raw_par[0], np.ndarray)):
            raise TypeError(f'parameter expected to be of scalar type, is {type(parameter)}')

        return raw_par, cls.generator(parameter[0])
        

class ConstantDistribution(ScalarValuedDistribution):
    """Distribution of a single value of any type (including strings) that does not vary.

    The value is the parameter; its standard deviation is zero. It can be varied in DSA but not in PSA.

    Used by [`ConstantVariable`][newsegsmodelframework.newsegsvariable.variable.ConstantVariable].
    """
    distribution = 'constant'
    parameterisations = [
        ConstantParameterisationDefault(),
    ]
    dsa_possible = True
    psa_possible = False

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """The central (deterministic) value of the variable.

        The parameter (exponentiated if the transform is `ln`).

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
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
    def std(cls, var: Variable) -> ScalarParam:
        """The standard deviation of the value.

        Always zero.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        return 0
    
    @classmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[ScalarParam, ScalarParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        return(cls.deterministic_value(var), cls.deterministic_value(var))

    @classmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarParam:
        """Draw a value for probabilistic sensitivity analysis.

        The deterministic value - a constant does not vary.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        if not isinstance(var, ConstantVariable):
            raise TypeError(f'Expecting var as ConstantVariable, is {type(var)}')
        
        return var.deterministic_value
    
    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[ScalarParam, ScalarParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Bounds that leave the value unchanged.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
            

class _NumericConstantParameterisation(Parameterisation):
    
    @classmethod
    @abstractmethod
    def generator(cls, *args, **kwargs) -> tuple[ScalarNumParam]:
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
    ) -> tuple[tuple[ScalarNumParam], tuple[ScalarNumParam]]:
        """Generate the parameters after a change to some of the raw parameters.

        Used when the user changes one parameter of a variable. The other parameters are adjusted (if `autoscale`) so that the set remains valid.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        ...


class NumericConstantParameterisationDefault(
    _NumericConstantParameterisation
):
    """Parameterisation of the numeric constant distribution by its `value`.

    Raw parameter: `value` - a single number.

    Native parameter: `(value,)`.

    Eligible when always.
    """
    names = ('value', )
    types = ('scalar', )
    defaults = (1., )
    
    @classmethod
    def generator(cls, value: Param, *args, **kwargs) -> tuple[ScalarNumParam]:
        """Convert the raw parameters to the native parameters.

        Raw parameter: `value` - a single number.

        Native parameter: `(value,)`.

        Args:
            value: The value.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
        if len(args):
            raise TypeError('Constant variable can only accept single value - use constant_vector for %s', args)
        if isinstance(value, str):
            raise ValueError('Numeric Constant variable can only accept numeric types - use constant')
        elif isinstance(value, Sequence):
            if len(value) > 1:
                raise ValueError('Constant variable can only accept single value - use constant_vector for %s', value)
            return (float(value[0]), )
        elif isinstance(value, np.ndarray):
            flat = value.flatten()
            if len(flat) > 1:
                raise ValueError('Constant variable can only accept single value - use constant_vector for %s', value)
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
    ) -> tuple[tuple[ScalarNumParam], tuple[ScalarNumParam]]:
        # As there is only a single parameter, there is no difference between setting a single parameter and all
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameter: `value` - a single number.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        raw_par = (parameter[0],)
        if isinstance(raw_par[0], str) or (isinstance(raw_par[0], Sequence) or isinstance(raw_par[0], np.ndarray)):
            raise TypeError(f'parameter expected to be of numeric scalar type, is {type(parameter)}')

        return raw_par, cls.generator(parameter[0]) # pyright: ignore[reportReturnType]


class NumericConstantDistribution(NumericScalarValuedDistribution):
    """Distribution of a single numeric value that does not vary.

    As `ConstantDistribution`, restricted to numbers, and so also able to be varied in optimisation.

    Used by [`NumericConstantVariable`][newsegsmodelframework.newsegsvariable.variable.NumericConstantVariable].
    """
    distribution = 'numeric_constant'
    parameterisations = [
        NumericConstantParameterisationDefault(),
    ]
    dsa_possible = True
    psa_possible = False

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
        if not isinstance(var, NumericConstantVariable):
            raise TypeError(f'Expecting var as NumericConstantVariable, is {type(var)}')
        if len(parameters) > 1 or len(parameters) < 1:
            raise TypeError(f'NumericConstantDistribution expects single scalar parameter, got {len(parameters)}')
        
        p0 = parameters[0]

        if isinstance(p0, str):
            raise TypeError(f'NumericConstantDistribution expects numeric parameter, got {type(p0)}')
        elif isinstance(p0, Sequence):
            if len(p0) == 0:
                raise ValueError('No parameter provided')
            elif len(p0) > 1:
                raise ValueError('Too many parameters. For a constant vector, set the variable_type to "vector" and then use a "constant_vector" distribution')
            if isinstance(p0[0], str):
                if not (var.transform[0] == 'identity'):
                    raise ValueError('constant value must have identity transform if it is a string')

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        """The central (deterministic) value of the variable.

        The parameter (exponentiated if the transform is `ln`).

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, NumericConstantVariable):
            raise TypeError(f'Expecting var as NumericConstantVariable, is {type(var)}')
        
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
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        Always zero.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        return 0
    
    @classmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        return(cls.deterministic_value(var), cls.deterministic_value(var))

    @classmethod
    def psa_value(cls, var: Variable, rng: np.random.Generator) -> ScalarNumParam:
        """Draw a value for probabilistic sensitivity analysis.

        The deterministic value - a constant does not vary.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        if not isinstance(var, NumericConstantVariable):
            raise TypeError(f'Expecting var as NumericConstantVariable, is {type(var)}')
        
        return var.deterministic_value
    
    @classmethod
    def dsa_auto_values(cls, var: Variable, interval: float = 0.95) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Bounds that leave the value unchanged.

        Args:
            var: The variable.
            interval: Probability mass within the interval (e.g. 0.95).

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
        if not isinstance(var, NumericConstantVariable):
            raise TypeError(f'Expecting var as NumericConstantVariable, is {type(var)}')
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
    """Parameterisation of the binomial distribution by `probability` and `trials`.

    Raw parameters: `probability` of success per trial, in [0, 1], and the number of `trials`, a non-negative integer.

    Native parameters: `(trials, probability)` - note the order.

    Eligible when always.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `probability` of success per trial, in [0, 1], and the number of `trials`, a non-negative integer.

        Native parameters: `(trials, probability)` - note the order.

        Args:
            probability: Probability of success in each trial.
            trials: Number of trials.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `probability` of success per trial, in [0, 1], and the number of `trials`, a non-negative integer.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
    """Parameterisation of the binomial distribution by the expected number of successes (`mean`) and `trials`.

    Raw parameters: `mean` - the expected number of successes, between 0 and `trials` - and the number of `trials`.

    Native parameters: `(trials, mean / trials)`.

    Eligible when always.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` - the expected number of successes, between 0 and `trials` - and the number of `trials`.

        Native parameters: `(trials, mean / trials)`.

        Args:
            mean: Mean.
            trials: Number of trials.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` - the expected number of successes, between 0 and `trials` - and the number of `trials`.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
    """Distribution of a number of successes in a number of independent trials (use one trial for a Bernoulli variable).

    The value is an integer between 0 and the number of trials. Only the identity transform is supported.

    Used by [`BinomialVariable`][newsegsmodelframework.newsegsvariable.variable.BinomialVariable].
    """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
        super().value_validation(var, *values)

        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if not (int(val) == val):
            raise ValueError(f'Binomial value expected to be integer, is {val}')
    
    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        """The central (deterministic) value of the variable.

        The expected number of successes `trials * probability`, rounded to a whole number.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        if var.transform[0] != 'identity':
            raise ValueError(f'Binomial distribution must provide values with identity transform, is {var.transform[0]}')
        return np.round(float(var.parameters[0]) * float(var.parameters[1]), 0) # NB - 0.5 rounds down
    
    @classmethod
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        The standard deviation of the number of successes.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        from scipy.stats import binom
        return float(binom.std(var.parameters[0], var.parameters[1]))
    
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
        """Draw a value for probabilistic sensitivity analysis.

        A binomial draw.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        if not isinstance(var, BinomialVariable):
            raise TypeError(f'Expecting var as BinomialVariable, is {type(var)}')
        
        return rng.binomial(int(var.parameters[0]), float(var.parameters[1]))
    
    @classmethod
    def dsa_auto_values(
        cls, 
        var: Variable, 
        interval: float = 0.95
    ) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Bounds are rounded to whole numbers between 0 and the number of trials.

        Args:
            var: The variable.
            interval: Probability mass within the interval (e.g. 0.95).

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
    """Parameterisation of the normal distribution by `mean` and standard deviation `sd`.

    Raw parameters: `mean` and `sd` (non-negative).

    Native parameters: `(mean, sd)`.

    Eligible when the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` and `sd` (non-negative).

        Native parameters: `(mean, sd)`.

        Args:
            mean: Mean.
            sd: Standard deviation.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` and `sd` (non-negative).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'identity'
    
class LogNormalParameterisationDefault(
    _NormalParameterisation
):
    """Parameterisation of the log-normal distribution by the `mu` and `sigma` of the underlying normal distribution.

    Raw parameters: `mu` and `sigma` (non-negative) - the mean and standard deviation of the logarithm of the value.

    Native parameters: `(mu, sigma)`.

    Eligible when the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mu` and `sigma` (non-negative) - the mean and standard deviation of the logarithm of the value.

        Native parameters: `(mu, sigma)`.

        Args:
            mu: Mean of the underlying normal distribution.
            sigma: Standard deviation of the underlying normal distribution.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mu` and `sigma` (non-negative) - the mean and standard deviation of the logarithm of the value.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'ln'

class LogNormalParameterisationExpected(
    _NormalParameterisation
):
    """Parameterisation of the log-normal distribution by the `mean` and `sd` of the value itself.

    Raw parameters: `mean` (positive) and `sd` (non-negative) of the log-normal value, not of its logarithm.

    Native parameters: `(mu, sigma)` of the underlying normal distribution, where `sigma^2 = ln(sd^2 / mean^2 + 1)` and `mu = ln(mean) - sigma^2 / 2`.

    Eligible when the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` (positive) and `sd` (non-negative) of the log-normal value, not of its logarithm.

        Native parameters: `(mu, sigma)` of the underlying normal distribution, where `sigma^2 = ln(sd^2 / mean^2 + 1)` and `mu = ln(mean) - sigma^2 / 2`.

        Args:
            mean: Mean.
            sd: Standard deviation.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` (positive) and `sd` (non-negative) of the log-normal value, not of its logarithm.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
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
    """Distribution of a normal distribution, or with the `ln` transform a log-normal distribution.

    With the `ln` transform the distribution is of the logarithm of the value, so the value is log-normal. Parameterisations are available by mean and standard deviation of the normal and of the log-normal.

    Used by [`NormalVariable`][newsegsmodelframework.newsegsvariable.variable.NormalVariable].
    """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        
        super().parameter_validation(var, *parameters)
        parameters = cast(tuple[ScalarNumParam, ScalarNumParam], parameters)

        if parameters[1] < 0:
            raise ValueError(f'Second parameter (sd/sigma) must be positive, is {parameters[1]}')

   # Value validation can be inherited from NumericScalarValuedDistribution

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        """The central (deterministic) value of the variable.

        The mean `mean` for an identity transform; for the `ln` transform the mean of the log-normal distribution, `exp(mu + sigma^2 / 2)`.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        if var.transform[0] == 'ln':
            return np.exp(var.parameters[0] + 0.5 * var.parameters[1]**2)
        else:
            return var.parameters[0]
    
    @classmethod
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        The parameter `sd`; for the `ln` transform the standard deviation of the log-normal distribution.

        Note:
            For the `ln` transform the native parameters `(mu, sigma)` are those of the
            underlying normal distribution, i.e. on the log scale. This is the scale on which
            maximum likelihood estimates, Jacobians and covariance matrices are naturally
            calculated, so it is the default parameterisation. The standard deviation returned
            is nevertheless that of the log-normal value, `exp(mu + sigma^2 / 2) * sqrt(exp(sigma^2) - 1)`,
            whichever parameterisation was used to set it.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        if var.transform[0] == 'ln':
            from scipy.stats import lognorm
            # NB - scipy's lognorm takes sigma as its shape, and exp(mu) as its scale
            mu, sigma = var.parameters
            return float(lognorm.std(sigma, scale = np.exp(mu)))
        else:
            return var.parameters[1]
    
    @classmethod
    def interval(cls, var: Variable, confidence: float = 0.95) -> tuple[ScalarNumParam, ScalarNumParam]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            var: The variable.
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        if not isinstance(var, NormalVariable):
            raise TypeError(f'Expecting var as NormalVariable, is {type(var)}')
        if var.transform[0] == 'ln':
            interval_function = _lognormal_interval
        else:
            interval_function = _normal_interval
        return interval_function(confidence, var.parameters)
    
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
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
        """Draw a value for probabilistic sensitivity analysis.

        A normal draw, or log-normal draw for the `ln` transform; the deterministic value if `sd` is zero.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
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
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.
            interval: Probability mass within the interval (e.g. 0.95).

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
    """Parameterisation of the beta distribution by its shape parameters `a` and `b`.

    Raw parameters: `a` and `b` (positive).

    Native parameters: `(a, b)`.

    Eligible when the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `a` and `b` (positive).

        Native parameters: `(a, b)`.

        Args:
            a: First shape parameter.
            b: Second shape parameter.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `a` and `b` (positive).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'identity'

class BetaParameterisationExpected(
    _BetaParameterisation
):
    """Parameterisation of the beta distribution by the `mean` and `sd` of the value.

    Raw parameters: `mean` in [0, 1] and `sd` in [0, 0.5].

    Native parameters: `(a, b)` with the requested mean and standard deviation.

    Eligible when the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` in [0, 1] and `sd` in [0, 0.5].

        Native parameters: `(a, b)` with the requested mean and standard deviation.

        Args:
            mean: Mean.
            sd: Standard deviation.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` in [0, 1] and `sd` in [0, 0.5].

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'identity'

class LogBetaParameterisationDefault(
    _BetaParameterisation
):
    """Parameterisation of the exponential of a beta-distributed value by the shape parameters of the beta distribution.

    Raw parameters: `a_log` and `b_log` (positive).

    Native parameters: `(a_log, b_log)`.

    Eligible when the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `a_log` and `b_log` (positive).

        Native parameters: `(a_log, b_log)`.

        Args:
            a_log: First shape parameter of the beta distribution of the logarithm.
            b_log: Second shape parameter of the beta distribution of the logarithm.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `a_log` and `b_log` (positive).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
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
    """Distribution of a beta distribution on [0, 1], e.g. a proportion or probability.

    With the `ln` transform the value is the exponential of a beta-distributed variable (not fully supported).

    Used by [`BetaVariable`][newsegsmodelframework.newsegsvariable.variable.BetaVariable].
    """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
        super().value_validation(var, *values)

        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if var.transform[0] != 'ln' and (val < 0 or val > 1):
            raise ValueError(f'Value expected in range [0, 1], is {val}')
        
    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        """The central (deterministic) value of the variable.

        The mean `a / (a + b)`; for the `ln` transform the expectation of `exp(X)`.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        a, b = var.parameters
        if var.transform[0] == 'ln':
            from scipy.stats import beta
            return float(beta.expect(np.exp, (a,b)))
        else:
            return a / (a + b)
    
    @classmethod
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        The standard deviation of the beta distribution. Not implemented for the `ln` transform.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        if not isinstance(var, BetaVariable):
            raise TypeError(f'Expecting var as BetaVariable, is {type(var)}')
        a, b = var.parameters
        from scipy.stats import beta
        
        if var.transform[0] == 'ln':
            raise NotImplementedError('Log beta distribution not fully supported.')
        else:
            return float(beta.std(a, b))

    # dsa_value can be inherited from NumericScalarValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> ScalarNumParam:
        """Draw a value for probabilistic sensitivity analysis.

        A beta draw (exponentiated for the `ln` transform); the deterministic value if `a` or `b` is zero.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
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
    """Parameterisation of the gamma distribution by `shape` and `scale`.

    Raw parameters: `shape` and `scale` (positive).

    Native parameters: `(shape, scale)`.

    Eligible when the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `shape` and `scale` (positive).

        Native parameters: `(shape, scale)`.

        Args:
            shape: Shape parameter.
            scale: Scale parameter.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `shape` and `scale` (positive).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'identity'
    
class GammaParameterisationExpected(
    _GammaParameterisation
):
    """Parameterisation of the gamma distribution by the `mean` and `sd` of the value.

    Raw parameters: `mean` and `sd` (positive).

    Native parameters: `(shape, scale)` with `shape = (mean / sd)^2` and `scale = mean / shape`.

    Eligible when the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` and `sd` (positive).

        Native parameters: `(shape, scale)` with `shape = (mean / sd)^2` and `scale = mean / shape`.

        Args:
            mean: Mean.
            sd: Standard deviation.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` and `sd` (positive).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'identity'

class LogGammaParameterisationDefault(
    _GammaParameterisation
):
    """Parameterisation of the exponential of a gamma-distributed value by the shape and scale of the gamma distribution.

    Raw parameters: `shape_log` and `scale_log` (positive).

    Native parameters: `(shape_log, scale_log)`.

    Eligible when the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `shape_log` and `scale_log` (positive).

        Native parameters: `(shape_log, scale_log)`.

        Args:
            shape_log: Shape parameter of the gamma distribution of the logarithm.
            scale_log: Scale parameter of the gamma distribution of the logarithm.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `shape_log` and `scale_log` (positive).

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return var.transform[0] == 'ln'

def _gamma_interval(
    interval: float,
    parameters: Sequence[ScalarNumParam]
) -> tuple[float, float]:
    if len(parameters) != 2:
        raise TypeError(f'Gamma requires two parameters, {len(parameters)} provided')
    
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
    """Distribution of a gamma distribution on positive values.

    With the `ln` transform the value is the exponential of a gamma-distributed variable.

    Used by [`GammaVariable`][newsegsmodelframework.newsegsvariable.variable.GammaVariable].
    """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
        super().value_validation(var, *values)

        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        
        values = cast(tuple[ScalarNumParam], values)
        val = values[0]
        if var.transform[0] == 'identity' and val < 0 :
            raise ValueError(f'Value expected to be positive, is {val}')

    @classmethod
    def deterministic_value(cls, var: Variable) -> ScalarNumParam:
        """The central (deterministic) value of the variable.

        The mean `shape * scale`; for the `ln` transform the expectation of `exp(X)`, found by numerical integration.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
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
    def std(cls, var: Variable) -> ScalarNumParam:
        """The standard deviation of the value.

        The standard deviation of the gamma distribution (of the exponential, for the `ln` transform).

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        from scipy.stats import gamma as gamma_dist
        shape, scale = var.parameters
        if var.transform[0] == 'ln':
            raise NotImplementedError('Log gamma distribution not fully supported')
        else:
            return float(gamma_dist.std(a = shape, scale = scale))
        
    @classmethod
    def dsa_value(cls, var: Variable, bound: DSA_BOUND) -> ScalarNumParam:
        """The value of the variable at a bound in deterministic sensitivity analysis.

        Args:
            var: The variable.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.

        Returns:
            The value at the requested bound.
        """
        if var.dsa_bounds_type == 'interval':


            if var.transform[0] == 'ln':
                if not isinstance(var, NumericScalarVariable):
                    raise TypeError(f'Expected NumericScalarVariable, got {type(var)}')

                interval_function = _loggamma_interval
                
                match bound:
                    case 'central':
                        return cast(float, super().dsa_value(var, bound))
                    case 'lower':
                        lbound, ubound = interval_function(float(var.dsa_lower), var.parameters)
                        if not np.isfinite(lbound):
                            return var.deterministic_value
                        return lbound
                    case 'upper':
                        lbound, ubound = interval_function(float(var.dsa_upper), var.parameters)
                        if not np.isfinite(ubound):
                            return var.deterministic_value
                        return ubound
                    case _:
                        raise ValueError(f'Unknown DSA bounds: {bound}')
            else:
                shape, scale = var.parameters
                if scale == 0:
                    return 0.
                elif shape == 0:
                    return scale # pyright: ignore[reportReturnType]
                else:
                    return super().dsa_value(var, bound)

        return super().dsa_value(var, bound)

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> ScalarNumParam:
        """Draw a value for probabilistic sensitivity analysis.

        A gamma draw (exponentiated for the `ln` transform).

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        if not isinstance(var, GammaVariable):
            raise TypeError(f'Expecting var as GammaVariable, is {type(var)}')
        
        shape, scale = var.parameters
        if scale == 0:
            return 0
        elif shape == 0:
            return scale
        
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
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.
            interval: Probability mass within the interval (e.g. 0.95).

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
    """Parameterisation of the constant vector distribution by its `values`.

    Raw parameter: `values` - a vector of values. Further positional arguments are appended to the vector.

    Native parameter: `(values,)`.

    Eligible when always.
    """
    names = ('values',)
    types = ('vector',)
    defaults = ([1], )

    @classmethod
    def generator(
        cls,
        values: VectorParam,
        *args, **kwargs
    ) -> tuple[VectorParam]:
        """Convert the raw parameters to the native parameters.

        Raw parameter: `values` - a vector of values. Further positional arguments are appended to the vector.

        Native parameter: `(values,)`.

        Args:
            values: The value(s) to check.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameter: `values` - a vector of values. Further positional arguments are appended to the vector.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        return parameter, cls.generator(parameter[0])
    

class ConstantVectorDistribution(VectorValuedDistribution):
    """Distribution of a vector of values that do not vary.

    The vector counterpart of `ConstantDistribution`. It can be varied in DSA but not in PSA.

    Used by [`ConstantVectorVariable`][newsegsmodelframework.newsegsvariable.variable.ConstantVectorVariable].
    """
    distribution = 'constant_vector'
    parameterisations: Sequence[_ConstantVectorParameterisation] = [ # pyright: ignore[reportIncompatibleVariableOverride]
        ConstantVectorParameterisationDefault(),
    ]

    dsa_possible = True
    psa_possible = False

    @classmethod
    def parameter_validation(cls, var: Variable, *parameters: Param) -> None:
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
        if len(parameters) != 1:
            raise TypeError(f'Single parameter sequence expected, got {len(parameters)} separate parameters')
        
        # Happy with pretty much anything else, even a sequence of sequences.
    
    @classmethod
    def value_validation(cls, var: Variable, *values: Value) -> None:
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
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
        """The central (deterministic) value of the variable.

        A copy of the vector of values.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
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
    
    @classmethod
    def std(cls, var: Variable) -> VectorParam:
        """The standard deviation of the value.

        A vector of zeros.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        return np.zeros_like(cls.deterministic_value(var))

    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> VectorParam:
        """Draw a value for probabilistic sensitivity analysis.

        The deterministic value - a constant does not vary.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
        if not isinstance(var, ConstantVectorVariable):
            raise TypeError(f'Expecting var as ConstantVectorVariable, is {type(var)}')
        return var.deterministic_value
    
    @classmethod
    def dsa_auto_values(cls, var: Variable) -> tuple[VectorParam, VectorParam]:
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Bounds that leave the values unchanged.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
        ...

class MultivariateNormalParameterisationDefault(
    _MultivariateNormalParameterisation
):
    """Parameterisation of the multivariate normal distribution by `mean` vector and variance-covariance matrix `vcv`.

    Raw parameters: `mean` and `vcv`, square with side the length of `mean`.

    Native parameters: `(mean, vcv)`.

    Eligible when no element of the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` and `vcv`, square with side the length of `mean`.

        Native parameters: `(mean, vcv)`.

        Args:
            mean: Mean.
            vcv: Variance-covariance matrix.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` and `vcv`, square with side the length of `mean`.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when no element of the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return all(trans == 'identity' for trans in var.transform)
    
class MultivariateLogNormalParameterisationDefault(
    _MultivariateNormalParameterisation
):
    """Parameterisation of the multivariate log-normal distribution by the `mu` vector and `vcv` of the underlying multivariate normal distribution.

    Raw parameters: `mu` and `vcv`, of the logarithm of the values.

    Native parameters: `(mu, vcv)`.

    Eligible when an element of the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mu` and `vcv`, of the logarithm of the values.

        Native parameters: `(mu, vcv)`.

        Args:
            mu: Mean of the underlying normal distribution.
            vcv: Variance-covariance matrix.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mu` and `vcv`, of the logarithm of the values.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when an element of the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return any(trans == 'ln' for trans in var.transform)
    
class MultivariateLogNormalParameterisationExpected(
    _MultivariateNormalParameterisation
):
    """Parameterisation of the multivariate log-normal distribution by the `mean` vector of the values, and `vcv` of the underlying normal distribution.

    Raw parameters: `mean`, `vcv` and `transform` (taken from the variable, not set by the user). Elements with an `ln` transform are converted to `mu = ln(mean) - vcv[i, i] / 2`.

    Native parameters: `(mu, vcv)`, with `mu` replaced by the converted value for elements with an `ln` transform.

    Eligible when an element of the transform is `'ln'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean`, `vcv` and `transform` (taken from the variable, not set by the user). Elements with an `ln` transform are converted to `mu = ln(mean) - vcv[i, i] / 2`.

        Native parameters: `(mu, vcv)`, with `mu` replaced by the converted value for elements with an `ln` transform.

        Args:
            mean: Mean.
            vcv: Variance-covariance matrix.
            transform: Transform(s) of the underlying distribution to the model value: `'identity'` or `'ln'` (the model value is the exponential of the distribution).
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
        if not isinstance(mean, np.ndarray):
            mean = np.asarray(mean, dtype = np.float64)
        if not isinstance(vcv, np.ndarray):
            vcv = np.asarray(vcv, dtype = np.float64)
        mean = mean.flatten()
        n_means = len(mean)
        vcv = vcv.reshape((n_means, n_means))

        if len(transform) < len(mean):
            extended_transforms = ['identity'] * len(mean)
            for i in range(len(mean)):
                if i < len(transform):
                    extended_transforms[i] = str(transform[i])
                else:
                    extended_transforms[i] = str(transform[-1])
            transform = extended_transforms

        for i, trans in enumerate(transform):
            if trans == 'ln':
                sigma_squared = vcv[i,i]
                mean[i] = np.log(mean[i]) - 0.5 * sigma_squared
        
        return (mean, vcv)

    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        """Whether the parameterisation can be used for a variable.

        Eligible when an element of the transform is `'ln'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return any(trans == 'ln' for trans in var.transform)

class MultivariateNormalDistribution(NumericVectorValuedDistribution):
    """Distribution of a multivariate normal distribution, with a variance-covariance matrix; each element may have an `ln` transform, making it log-normal.

    DSA varies one element (`dsa_value_index`) of the vector at a time.

    Used by [`MultivariateNormalVariable`][newsegsmodelframework.newsegsvariable.variable.MultivariateNormalVariable].
    """
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
        """Bounds of the central interval of the distribution.

        Args:
            interval: Probability mass within the interval (e.g. 0.95).
            var: The variable.

        Returns:
            The lower and upper bounds.
        """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
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
        """The central (deterministic) value of the variable.

        The mean vector; elements with an `ln` transform are the mean of the log-normal, `exp(mu_i + vcv[i, i] / 2)`.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, MultivariateNormalVariable):
            raise TypeError(f'Expecting var as MultivariateNormalVariable, is {type(var)}')
        var = cast(MultivariateNormalVariable, var)
        
        oarray = np.asarray(var.parameters[0]).flatten()
        vcv = var.parameters[1]


        for i, trans in enumerate(var.transform):
            if trans == 'ln':
                if not isinstance(vcv, np.ndarray):
                    vcv = np.reshape(np.array(vcv), (len(oarray), len(oarray)))

                oarray[i] = np.exp(oarray[i] + 0.5 * vcv[i,i])
        return oarray
    
    @classmethod
    def std(cls, var: Variable) -> NumericVectorParam:
        """The standard deviation of the value.

        The square roots of the diagonal of the variance-covariance matrix; for elements with an `ln` transform the standard deviation of the log-normal.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        if not isinstance(var, MultivariateNormalVariable):
            raise TypeError(f'Expecting var as MultivariateNormalVariable, is {type(var)}')
        
        oarray = np.sqrt(np.diag(var.parameters[1]))
        mu = np.asarray(var.parameters[0]).flatten()
        for i, trans in enumerate(var.transform):
            if trans == 'ln':
                s2 = oarray[i]**2
                m = mu[i]
                v = (np.exp(s2) - 1.)*np.exp(2.*m+s2)
                oarray[i] = np.sqrt(v)
        return oarray
    
    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> NumericVectorParam:
        """Draw a value for probabilistic sensitivity analysis.

        A multivariate normal draw, with elements exponentiated where the transform is `ln`.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
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
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
        """Convert raw parameters into the native parameters of the distribution.

        Args:
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
        ...

class DirichletParameterisationDefault(
    _DirichletParameterisation
):
    """Parameterisation of the Dirichlet distribution by its concentration parameters `alpha`.

    Raw parameter: `alpha` - vector of at least two non-negative concentration parameters.

    Native parameter: `(alpha,)`.

    Eligible when every element of the transform is `'identity'`.
    """
    names = ('alpha',)
    types = ('vector',)
    defaults = ([0.5, 0.5], )

    @classmethod
    def generator(
        cls,
        alpha: NumericVectorParam,
        *args, **kwargs
    ) -> tuple[NumericVectorParam, ]:
        """Convert the raw parameters to the native parameters.

        Raw parameter: `alpha` - vector of at least two non-negative concentration parameters.

        Native parameter: `(alpha,)`.

        Args:
            alpha: Vector of concentration parameters.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameter: `alpha` - vector of at least two non-negative concentration parameters.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
        return parameter, cls.generator(parameter[0]) # pyright: ignore[reportReturnType, reportArgumentType]
    
    @classmethod
    def eligibility(cls, var: Variable) -> bool:
        """Whether the parameterisation can be used for a variable.

        Eligible when every element of the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return all(trans == 'identity' for trans in var.transform)
    
class DirichletParameterisationExpected(
    _DirichletParameterisation
):
    """Parameterisation of the Dirichlet distribution by the `mean` vector (which sums to 1) and `vcv` of the values.

    Raw parameters: `mean` and `vcv`. The concentration parameters are fitted (`fit_dirichlet`) to the variances; an `ArithmeticError` is raised if the means cannot be recovered.

    Native parameter: `(alpha,)`.

    Eligible when every element of the transform is `'identity'`.
    """
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
        """Convert the raw parameters to the native parameters.

        Raw parameters: `mean` and `vcv`. The concentration parameters are fitted (`fit_dirichlet`) to the variances; an `ArithmeticError` is raised if the means cannot be recovered.

        Native parameter: `(alpha,)`.

        Args:
            mean: Mean.
            vcv: Variance-covariance matrix.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The native parameters.
        """
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

        alpha = np.asarray(fit_dirichlet(mean, vcv))
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
        """Generate the parameters after a change to some of the raw parameters.

        Raw parameters: `mean` and `vcv`. The concentration parameters are fitted (`fit_dirichlet`) to the variances; an `ArithmeticError` is raised if the means cannot be recovered.

        Raises `ValueError` if the new value is not valid for the parameter.

        Args:
            parameter: The new raw parameter value(s), in a tuple.
            parameter_index: Indices of the raw parameters being set.
            current_params: The raw parameters currently held.
            autoscale: If the new value would be inconsistent with the other parameters, adjust the others to accommodate it rather than raising an error.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.

        Returns:
            The raw parameters and the native parameters.
        """
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
        """Whether the parameterisation can be used for a variable.

        Eligible when every element of the transform is `'identity'`.

        Args:
            var: The variable.

        Returns:
            True if eligible.
        """
        return all(trans == 'identity' for trans in var.transform)

class DirichletDistribution(NumericVectorValuedDistribution):
    """Distribution of a Dirichlet distribution - a vector of probabilities which sum to 1 (a simplex).

    DSA varies one element (`dsa_value_index`) of the vector, scaling the others to preserve the sum. Only the identity transform is supported.

    Used by [`DirichletVariable`][newsegsmodelframework.newsegsvariable.variable.DirichletVariable].
    """
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
        """Bounds of the central interval of the distribution.

        Treats the element at `dsa_value_index` as beta distributed with parameters `alpha_i` and `sum(alpha) - 1`, and scales the other elements so the vector still sums to 1.

        Args:
            interval: Probability mass within the interval (e.g. 0.95).
            var: The variable.

        Returns:
            The lower and upper bounds.
        """
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
        """Check that the native parameters are valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *parameters: The parameters, in native form.
        """
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
        """Check that a value is valid for this distribution.

        Raises `TypeError` or `ValueError` if not.

        Args:
            var: The variable.
            *values: The value(s) to check.
        """
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
        
        checksum = np.abs(np.sum(val) - 1) # type: ignore
        if checksum > 1e-12:
            raise ValueError(f'Dirichlet values should sum to 1, these sum to {np.sum(val)}') # type: ignore
        
    @classmethod
    def deterministic_value(cls, var: Variable) -> NumericVectorParam:
        """The central (deterministic) value of the variable.

        The mean `alpha / sum(alpha)`. The `ln` transform is not implemented.

        Args:
            var: The variable.

        Returns:
            The deterministic value, after applying any transform.
        """
        if not isinstance(var, DirichletVariable):
            raise TypeError(f'Expecting var as DirichletVariable, is {type(var)}')
        var = cast(DirichletVariable, var)
        
        if any(trans == 'ln' for trans in var.transform):
            raise NotImplementedError('Log transform not implemented for Dirichlet distribution')

        oarray = np.asarray(var.parameters[0]).flatten()
        return oarray / np.sum(oarray)
    
    @classmethod
    def std(cls, var: Variable) -> NumericVectorParam:
        """The standard deviation of the value.

        The standard deviation of the values. The `ln` transform is not implemented.

        Args:
            var: The variable.

        Returns:
            The standard deviation (a vector for a vector variable).
        """
        if not isinstance(var, DirichletVariable):
            raise TypeError(f'Expecting var as DirichletVariable, is {type(var)}')
        
        if any(trans == 'ln' for trans in var.transform):
            raise NotImplementedError('Log transform not implemented for Dirichlet distribution')
        
        from scipy.stats import dirichlet_multinomial
        return np.sqrt(dirichlet_multinomial.var(var.parameters,1))

    # dsa_value should inherit from VectorValuedDistribution

    @classmethod
    def psa_value(
        cls, 
        var: Variable, 
        rng: Generator
    ) -> NumericVectorParam:
        """Draw a value for probabilistic sensitivity analysis.

        A Dirichlet draw; zero concentration parameters give zero probability.

        Args:
            var: The variable.
            rng: Random number generator from which to draw.

        Returns:
            The value drawn.
        """
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
        """Default lower and upper bounds for deterministic sensitivity analysis, according to the `dsa_bounds_type` of the variable.

        For a `relative` bound the defaults are 0.9 and 1.1 of the central value; for an `offset` or `absolute` bound they come from the confidence interval.

        Args:
            var: The variable.

        Returns:
            The default lower and upper bounds, to be interpreted according to `dsa_bounds_type`.
        """
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
    """Read the value of a parameter from a model or finance.

    The section is a dotted path of attributes (or mapping keys) from the model; a sequence of parameters gives a list of values.

    Args:
        model: The energy model or finance model.
        model_section: Dotted path from the model to the object holding the parameter (`None` or `''` for the model itself).
        model_parameter: Name of the parameter.

    Returns:
        The value(s).
    """
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
    """Set a parameter of a model or finance.

    Builds a nested dictionary from the dotted section and parameter and passes it to `model.update`.

    Args:
        value: The value.
        model: The energy model or finance model.
        model_section: Dotted path from the model to the object holding the parameter (`None` or `''` for the model itself).
        model_parameter: Name of the parameter.
    """
    update_dict = {}
    last_dict = update_dict
    if model_section is not None and model_section != '':
        model_sec_chain = str(model_section).split('.')
        for key in model_sec_chain:
            last_dict[key] = {}
            last_dict = last_dict[key]
    
    last_dict[model_parameter] = value
    model.update(update_dict)

@revision_dataclass
class VariableConfig(DataWithRevision):
    # Don't include parameters as well as raw, or update will trigger two revisions
    #parameters: ParamList | None = None
    """Revision-tracked configuration of a `Variable`: the parts that change under user control.

    Attributes:
        raw_parameters: The parameters as set by the user, in the form of the current parameterisation.
        dsa_selected: If DSA is possible and the variable is selectable, whether it is selected.
        dsa_bounds_type: How the DSA bounds are specified: `absolute`, `offset`, `relative` or `interval`.
        psa_selected: If PSA is possible and the variable is selectable, whether it is selected.
        optim_selected: Whether the variable is varied in optimisation.
    """
    raw_parameters: ParamList | None = None

    dsa_selected: bool = False
    """
    If possible and selectable, has variable been selected?
    """
    dsa_bounds_type: DSA_BOUNDS_TYPE = 'absolute'
    psa_selected: bool = False
    """
    If possible and selectable, has variable been selected for PSA?
    """
    optim_selected: bool = False
    """
    Is the variable selected for variation in optimisation?
    """


class Variable(
    NewsegsComponent
):
    """A single unit of variation in a model.

    May be associated with a single parameter, or a group of parameters that must co-vary (e.g. the
    parameters of a statistical distribution, or a set of probabilities which form a simplex).
    A `Variable` is a [`NewsegsComponent`][newsegsmodelframework.core.NewsegsComponent] so is
    serialisable and revision-tracked. The subclass, and the statistical behaviour, is chosen by
    the `distribution` argument: `Variable(name, distribution = 'normal')` returns a `NormalVariable`.

    See the [module documentation][newsegsmodelframework.newsegsvariable.variable] for an overview.

    **Identity and location.** `interface_section`, `interface_key` and `interface_subindex`
    identify the variable in the interface and in a metamodel; together they form the *varid*
    `{section}.{key}.{subindex}`. `model_section` and `model_parameter` locate the parameter(s)
    of the model or finance (`configuration_type`) that it sets. A vector variable may set several
    parameters, by giving sequences of parameters (and sections).

    **Parameters.** The user-facing *raw parameters* (`raw_parameters`) are in the form of the
    current parameterisation (`parameterisation_index` into the list of parameterisations of the
    distribution that are eligible for the transform). They are converted to the *native*
    `parameters` of the distribution when set.

    **Values.** `deterministic_value` is the central value. `get_dsa_value` returns the lower, central
    or upper value for DSA and `draw_psa` / `get_psa_value` the value of a PSA draw; both return the
    deterministic value unless the variable is selected and active for the analysis.
    `update_model` and its relatives write the appropriate value into a model.

    Attributes:
        name: Name of the variable.
        label: Display label; the name if none has been set.
        unit: Unit of measurement of the value(s).
        icon_name: Name(s) of the icon(s) used in the interface.
        configuration_type: Whether the variable sets a parameter of the `model` or the `finance`.
        distribution: The (stateless) distribution.
        parameterisation_index: Index of the parameterisation in use.
        value_name: Names of the individual values of a vector variable.
        value_formatter: Function giving a sensible string for a value.
        formatter_dp: Decimal places of the default format of a numeric value.
        interface_min: Minimum value of the input field.
        interface_max: Maximum value of the input field.
        interface_step: Step of the input field.
        configuration_show: Whether to show an input on the model configuration page.
        dsa_selectable: Whether the variable can be selected for DSA.
        dsa_active: Whether the system is running a DSA.
        dsa_focussed: Whether the variable is the one being varied in the current DSA run.
        psa_selectable: Whether the variable can be selected for PSA.
        psa_active: Whether the system is running a PSA.
        optim_selectable: Whether the variable can be varied in optimisation.
        optim_min: Lower limit for optimisation.
        optim_max: Upper limit for optimisation.
        variable_type: `scalar` or `vector`.
        soft_dirty: Flags the variable for storage without dirtying the components that depend upon it.
    """
    distribution: Distribution
    parameterisation_index: int
    
    value_formatter = '{:}'.format
    """
    Function for sensible formatting of the value
    """

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
    #dsa_selected: bool = False
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

    #dsa_bounds_type: DSA_BOUNDS_TYPE = 'absolute'

    psa_selectable: bool = False
    """
    If possible, is variable selectable as part of PSA?
    """
    #psa_selected: bool = False
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

    optim_selectable: bool = False
    """
    Can the variable be varied as part of system optimisation?

    (Current implementations will vary the first parameter of scalar variables in optimisation)
    """
    #optim_selected: bool = False
    """
    Is the variable selected for variation in optimisation?
    """
    _optim_show: bool = False
    """
    Is the variable to be shown in the opimisation configuration container?
    """
    optim_min = 0
    optim_max = None

    variable_type: VARIABLE_TYPE = 'scalar'
    _label: str | None = None

    # NewsegsComponent constants
    _id_prefix = COMPONENT_PREFIXES['variable']
    # SerialiseToDictMixin constants
    _constructor_class = 'Variable'

    soft_dirty: bool = False
    """Soft indicator to flag the variable for upsert to storage without dirtying dependent components."""

    @override
    def _generate_config(self, *args, **kwargs) -> VariableConfig:
        return VariableConfig(*args, **kwargs)
    _config: VariableConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __new__(
        cls,
        *args,
        distribution: VARIABLE_DISTRIBUTION = 'constant',
        **kwargs
    ):
        """Create the subclass of `Variable` for the requested `distribution`.

        Args:
            distribution: The distribution, selecting the subclass; one of `VARIABLE_DISTRIBUTION`.
            *args: Further positional arguments.
            **kwargs: Further keyword arguments.
        """
        subclasses = {
            'constant': ConstantVariable,
            'numeric_constant': NumericConstantVariable,
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
        *args,
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
        #parameters: ParamList | None = None,
        default_parameters: ParamList | None = None,
        value_name: Sequence[str]| None = None,
        configuration_show: bool = True,
        dsa_show: bool = False,
        psa_show: bool = False,
        #dsa_bounds_type: DSA_BOUNDS_TYPE = 'absolute',
        dsa_lower: Value | None = None,
        dsa_upper: Value | None = None,
        dsa_selectable: bool = False,
        #dsa_selected: bool = False,
        dsa_active: bool = False,
        dsa_focussed: bool = False,
        psa_selectable: bool = False,
        #psa_selected: bool = False,
        psa_active: bool = False,
        interface_min: float | None = None,
        interface_max: float | None = None,
        interface_step: float | None = None,
        formatter_dp: int | None = None,
        optim_selectable: bool = False,
        #optim_selected: bool = False,
        optim_show: bool = False,
        **kwargs
    ):
        """Create a variable.

        Args:
            name: Name of the variable.
            label: Display label; defaults to the name.
            unit: Unit of measurement of the value(s).
            icon_name: Name(s) of the icon(s) used in the interface.
            configuration_type: Whether the variable sets a parameter of the `model` or of the `finance`.
            model_section: Dotted path to the object in the model that holds the parameter (a sequence if different parameters are in different sections).
            model_parameter: Name(s) of the model parameter(s) set by the variable; defaults to `name`.
            interface_section: Section of the interface (part of the varid).
            interface_key: Key within the section (part of the varid); defaults to `name`.
            interface_subindex: Distinguishes several instances of the same key (part of the varid).
            distribution: The distribution of the variable; selects the subclass.
            transform: Transform(s) from the distribution to the model value: `identity` or `ln`.
            parameterisation_index: Which parameterisation of the distribution to use; defaults to the first eligible for the transform.
            default_parameters: The default raw parameters, to which `reset_parameters` returns; defaults to the initial parameters.
            value_name: Names for the individual values of a vector variable.
            configuration_show: Whether to show an input on the model configuration page.
            dsa_show: Whether to show an input on the DSA page.
            psa_show: Whether to show an input on the PSA page.
            dsa_lower: Lower DSA bound; defaults to a value from `dsa_auto_values`.
            dsa_upper: Upper DSA bound; defaults to a value from `dsa_auto_values`.
            dsa_selectable: Whether the variable can be selected for DSA.
            dsa_active: Whether the system is running a DSA.
            dsa_focussed: Whether this is the variable varying in the present DSA run.
            psa_selectable: Whether the variable can be selected for PSA.
            psa_active: Whether the system is running a PSA.
            interface_min: Minimum value of the input field.
            interface_max: Maximum value of the input field.
            interface_step: Step of the input field.
            formatter_dp: Decimal places for formatting numeric values.
            optim_selectable: Whether the variable can be varied in optimisation.
            optim_show: Whether to show an input in the optimisation configuration.
            **kwargs: Further configuration, e.g. `raw_parameters`.
        """
        if 'parameters' in kwargs:
            if not 'raw_parameters' in kwargs:
                kwargs['raw_parameters'] = kwargs.pop('parameters')

        super().__init__(*args, **kwargs)
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
        #self.dsa_bounds_type = dsa_bounds_type

        if self.raw_parameters is None:
            self._set_initial_parameters()
        else:
            if isinstance(self.raw_parameters, str) or not isinstance(self.raw_parameters, Sequence):
                self.set_parameters(self.raw_parameters)
            else:
                self.set_parameters(*self.raw_parameters)

        if default_parameters is None:
            self.replace_default_parameters()
        else:
            if isinstance(default_parameters, str) or not isinstance(default_parameters, Sequence):
                self._set_default_parameters(default_parameters)
            else:
                self._set_default_parameters(*default_parameters)

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
        #self.dsa_selected = dsa_selected
        self.dsa_active = dsa_active
        self.dsa_focussed = dsa_focussed
        self._dsa_show = dsa_show

        if value_name is None:
            self.value_name = [f'Value {i+1}' for i in range(self.n_values)]
        else:
            self.value_name = value_name

        self.psa_selectable = psa_selectable
        #self.psa_selected = psa_selected
        self.psa_active = psa_active
        self._psa_show = psa_show

        self.optim_selectable = optim_selectable
        #self.optim_selected = optim_selected
        self._optim_show = optim_show

        self.configuration_show = configuration_show
        self.interface_min = interface_min
        self.interface_max = interface_max
        self.interface_step = interface_step

        if formatter_dp is not None:
            self.formatter_dp = formatter_dp

    @property
    def label(self) -> str:
        """Display label of the variable; the name if no label has been set.
        """
        if self._label is None:
            return self.name
        return self._label
    
    @label.setter
    def label(self, label: str) -> None:
        self._label = label

    @property
    def parameterisation(self) -> Parameterisation:
        """The `Parameterisation` in use.
        """
        if self.parameterisation_index is None:
            raise AttributeError('No parameterisation index set')
        return self.distribution.parameterisations[self.parameterisation_index]

    def _get_native_parameters(self) -> tuple[ScalarParam | VectorParam | MatrixParam, ...]:
        #p = self._config.parameters
        p = self._parameters
        if p is not None:
            if isinstance(p, Iterable):
                return tuple(p)
            else:
                return (p,)
        raise AttributeError('Parameters not yet set')

    def _set_native_parameters(self, parameters: ParamList) -> None:
        #self._config.parameters = parameters
        self._parameters = parameters

    @property
    def parameters(self) -> tuple[ScalarParam | VectorParam | MatrixParam, ...]:
        """The native parameters of the distribution.
        """
        return self._get_native_parameters()

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        self._set_native_parameters(parameters)

    def set_parameters(self, *parameters: Param):
        """Set the parameters from raw parameters.

        The raw parameters are converted by the current parameterisation into native parameters, which are validated by the distribution. The raw parameters are stored in the configuration.

        Args:
            *parameters: The parameters, in native form.
        """
        raw_parameters = copy.copy(parameters)
        
        native_params = self.distribution.parameterisations[self.parameterisation_index].generator(*parameters)
        self.distribution.parameter_validation(self, *native_params)

        self.raw_parameters = raw_parameters # The part which is stored in the config
        self.parameters = native_params

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
            self.raw_parameters = raw_parameters
            self.parameters = native_parameters
        except (ValueError, TypeError):
            return False, self.raw_parameters
        return True, self.raw_parameters
    
    @property
    @abstractmethod
    def transform(self) -> tuple[VARIABLE_TRANSFORM, ...]:
        """The transform from distribution to model value for each value: `identity` or `ln`.
        """
        ...

    @abstractmethod
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        """Set the transform from the distribution to the model value.

        An `'ln'` transform makes the model value the exponential of the distribution.

        Args:
            transform: Transform(s) of the underlying distribution to the model value: `'identity'` or `'ln'` (the model value is the exponential of the distribution).
            autosize: If true and a single transform is given for a vector variable, repeat it for every value.
        """
        ...
    
    def get_deterministic_value(self) -> Value:
        """The central value, validated by the distribution.

        Returns:
            The deterministic value.
        """
        v = self.distribution.deterministic_value(self)
        self.distribution.value_validation(self, v)
        return v

    @property
    def deterministic_value(self) -> Value:
        """The central (deterministic) value of the variable, used in an ordinary model run.
        """
        return self.get_deterministic_value()
    
    def get_std(self) -> Value:
        """The standard deviation of the value.

        Returns:
            The standard deviation.
        """
        v = self.distribution.std(self)
        return v
    
    def get_confidence_interval(self, confidence: float = 0.95) -> tuple[Value, Value]:
        """Bounds of the central interval of the distribution of the value.

        Args:
            confidence: Probability mass within the interval (e.g. 0.95).

        Returns:
            The lower and upper bounds.
        """
        v = self.distribution.interval(self, confidence)
        return v

    def set_distribution(self) -> None:
        """Hook for subclasses to set up after the distribution is known. Does nothing.
        """
        pass

    @property
    def dsa_possible(self) -> bool:
        """Whether the distribution allows the variable to be varied in DSA.
        """
        return self.distribution.dsa_possible
    
    @property
    def psa_possible(self) -> bool:
        """Whether the distribution allows the variable to be drawn in PSA.
        """
        return self.distribution.psa_possible
    
    @property
    def optim_possible(self) -> bool:
        """Whether the distribution allows the variable to be varied in optimisation.
        """
        return self.distribution.optim_possible
    
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

    @property
    def optim_show(self) -> bool:
        """
        True if an input field should be created in the optim configuration container

        NB - even if `.optim_show` is set `True`, cannot return `True` if not
        `.optim_possible` or not `.optim_selectable`
        """
        return self._optim_show and self.optim_possible and self.optim_selectable
    
    @optim_show.setter
    def optim_show(self, show: bool) -> None:
        self._optim_show = show
    
    def get_indexed_parameterisations(self):
        """The parameterisations that can be used with the transform of the variable.

        Returns:
            List of dictionaries with the `index` into the parameterisations of the distribution and the `parameterisation`.
        """
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
    
    def _set_initial_parameters(self):
        parameterisation = self.distribution.parameterisations[self.parameterisation_index]
        defaults = parameterisation.defaults
        if isinstance(defaults, str) or not isinstance(defaults, Sequence):
            self.set_parameters(defaults)
        else:
            self.set_parameters(*defaults)
    
    def _set_default_parameters(self, *parameters: Param):
        """
        Set the default parameters

        Parameters must be in native format.
        Generally used to store the present values of the parameters.
        """
        self._default_parameters = parameters

    def reset_parameters(self, parameter_index: int | None = None):
        """Return the parameters to their defaults.

        The defaults are those set by `replace_default_parameters` or `default_parameters`.

        Args:
            parameter_index: Indices of the raw parameters being set.
        """
        if parameter_index is None:
            self.set_parameters(*self._default_parameters)
        else:
            p0 = list(copy.copy(self.parameters))
            if parameter_index >= 0 and parameter_index <= len(p0):
                p0[parameter_index] = self._default_parameters[parameter_index]
            elif parameter_index < 0 and -parameter_index < len(p0):
                p0[parameter_index] = self._default_parameters[parameter_index]
            self.set_parameters(*p0)

    def replace_default_parameters(self):
        """
        Set the current parameters as defaults
        """
        if isinstance(self.raw_parameters, str) or not isinstance(self.raw_parameters, Sequence):
            self._set_default_parameters(self.raw_parameters)
        else:
            self._set_default_parameters(*self.raw_parameters)

    @property
    def n_values(self) -> int:
        """The number of values the variable provides: 1 for a scalar variable.
        """
        return self.distribution.n_values(self)
    
    @property
    def dsa_lower(self) -> Value:
        """The lower DSA bound, interpreted according to `dsa_bounds_type`.
        """
        return self._dsa_lower
    
    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> Value:
        """The upper DSA bound, interpreted according to `dsa_bounds_type`.
        """
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
        ) -> Value:
        """Draw a value for probabilistic sensitivity analysis.

        The draw is stored and returned by `get_psa_value`. If the variable is not PSA-possible, selectable, selected and active, the deterministic value is returned. A draw which fails validation is retried; if all fail the deterministic value is used and a warning issued.

        Args:
            rng: Random number generator from which to draw.
            retries: Number of attempts to draw a valid value before falling back to the deterministic value.

        Returns:
            The value drawn.
        """
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
        """The value from the last PSA draw.

        The deterministic value if the variable is not being varied in a PSA.

        Returns:
            The value.
        """
        if (
            self.distribution.psa_possible
            and self.psa_selectable
            and self.psa_selected
            and self.psa_active
        ):
            return self._psa_draw
        return self.deterministic_value
    
    def is_model_type(self, model: ModelType) -> bool:
        """Whether the model is of the type that the variable sets.

        Compares `configuration_type` (`'model'` or `'finance'`) with the type of the model.

        Args:
            model: The energy model or finance model.

        Returns:
            True if the variable applies to the model.
        """
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
        """Set the model parameter(s) to the deterministic value(s).

        Equivalent to `update_model_deterministic`.

        Args:
            model: The energy model or finance model.
        """
        self.update_model_deterministic(model)

    def update_model_deterministic(self, model: ModelType) -> None:
        """
        Set the associated parameter(s) in the model/finance to deterministic value(s).
        """
        if not self.is_model_type(model):
            return
        self._update_model(model, self.deterministic_value)

    def update_model_dsa(self, model: ModelType, bound: DSA_BOUND) -> None:
        """Set the associated parameter(s) in the model or finance to the DSA value at a bound.

        Does nothing if the variable is not for that type of model.

        Args:
            model: The energy model or finance model.
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.
        """
        if not self.is_model_type(model):
            return
        val = self.get_dsa_value(bound)
        self._update_model(model, val)

    def update_model_psa(self, model: ModelType) -> None:
        """Set the associated parameter(s) in the model or finance to the value of the last PSA draw.

        Does nothing if the variable is not for that type of model.

        Args:
            model: The energy model or finance model.
        """
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
        """Update the state from a dictionary, restoring parameters to tuples after serialisation as JSON.

        Args:
            config: Dictionary of the serialised state.
        """
        super().update(config)
        # Convert required attributes to tuple in case they have come from json
        if isinstance(config, dict):
            if '_config' in config:
                cfg = config.get('_config',{})
                if 'raw_parameters' in cfg:
                    self.raw_parameters = tuple(self.raw_parameters)
                if 'parameters' in cfg:
                    self.parameters = tuple(self.parameters)
            if '_transform' in config:
                self._transform = tuple(self._transform)

    def __deepcopy__(self, memo):
        """Deep copy of the variable.

        Args:
            memo: Memo dictionary of `copy.deepcopy`.
        """
        o = Variable(self.name, distribution = self.distribution.distribution) # pyright: ignore[reportAbstractUsage]
        o.__dict__.update(copy.deepcopy(self.__dict__)) # pyright: ignore[reportAttributeAccessIssue]
        return o
    
    def __reduce__(self) -> str | tuple[Any, ...]:
        """Reduce for pickling: recreate with the name and distribution and restore the state.
        """
        return (
            _recover_variable, # Callable for initial object version # pyright: ignore[reportAbstractUsage]
            (self.name, self.distribution.distribution), # Args for initial construction
            self.__dict__,
        )

    @override
    def json_dumps(self) -> str:
        """Serialise the variable to a JSON string.
        """
        return json.dumps(self.to_dict(), cls = jsonfuncs.NumpyEncoder)

def _recover_variable(name, dist):
    """
    When restoring variable from a reduced form, use this simple two-parameter constructor
    """
    return Variable(name, distribution = dist) # pyright: ignore[reportAbstractUsage]

class ScalarVariable(Variable):

    """A variable with a single value.
    """
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
        """The lower DSA bound, a single value.
        """
        return self._dsa_lower

    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> ScalarParam:
        """The upper DSA bound, a single value.
        """
        return self._dsa_upper

    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_upper = value

    @property
    def transform(self) -> tuple[VARIABLE_TRANSFORM]:
        """The transform: a one-element tuple.
        """
        return self._transform
    
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        """Set the transform from the distribution to the model value.

        A single transform, or a sequence of one.

        Args:
            transform: Transform(s) of the underlying distribution to the model value: `'identity'` or `'ln'` (the model value is the exponential of the distribution).
            autosize: If true and a single transform is given for a vector variable, repeat it for every value.
        """
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
        """The central value of the variable.
        """
        return cast(ScalarParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> ScalarParam:
        """The value at a bound for deterministic sensitivity analysis.

        See `Variable.get_dsa_value`.

        Args:
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.
            force: Return the DSA value even if the variable is not currently selected, active and focussed for DSA.

        Returns:
            The value at the requested bound.
        """
        return cast(ScalarParam, super().get_dsa_value(bound, force))


class NumericScalarVariable(ScalarVariable):
    """A variable with a single numeric value.
    """
    distribution: NumericScalarValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]

    formatter_dp = 1
    @property
    def value_formatter(self) -> Callable[[float|int], str]:        
        """
        Function for sensible formatting of the value or bound
        """
        fstring = '{:,.' + f'{self.formatter_dp:d}'+'f}'   
        return fstring.format

    @override
    def _validate_bound(self, value: Value) -> ScalarNumParam:
        v = super()._validate_bound(value)
        if v is None:
            raise TypeError(f'DSA bound should be a numeric value, got None')
        if not isinstance(v, ScalarNumParam):
            raise TypeError(f'DSA bound should be a numeric value, is {type(v)}')
        return v

    @property
    @override
    def parameters(self) -> tuple[ScalarNumParam, ...]:
        """The native parameters of the distribution, as numbers.
        """
        return cast(tuple[ScalarNumParam, ...], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)

    @property
    def deterministic_value(self) -> ScalarNumParam:
        """The central value of the variable.
        """
        return cast(ScalarNumParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> ScalarNumParam:
        """The value at a bound for deterministic sensitivity analysis.

        See `Variable.get_dsa_value`.

        Args:
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.
            force: Return the DSA value even if the variable is not currently selected, active and focussed for DSA.

        Returns:
            The value at the requested bound.
        """
        return cast(ScalarNumParam, super().get_dsa_value(bound, force))


class TwoParamNumericScalarVariable(NumericScalarVariable):
    """A numeric variable whose distribution has two scalar parameters.
    """
    distribution: TwoParamNumericScalarValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    @override
    def parameters(self) -> tuple[ScalarNumParam, ScalarNumParam]:
        """The two native parameters of the distribution.
        """
        return cast(tuple[ScalarNumParam, ScalarNumParam], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)
    

class VectorVariable(Variable):

    """A variable with a vector of values.
    """
    distribution: VectorValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_lower: VectorParam
    _dsa_upper: VectorParam
    _transform: tuple[VARIABLE_TRANSFORM, ...]

    variable_type = 'vector'

    @property
    @override
    def parameters(self) -> tuple[VectorParam | MatrixParam, ...]:
        """The native parameters of the distribution, which may be vectors or matrices.
        """
        return cast(tuple[VectorParam, ...], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)

    def set_parameters(
        self, 
        *parameters: Param,
    ):
        """Set the parameters from raw parameters, resizing the transform to the number of values.

        Args:
            *parameters: The parameters, in native form.
        """
        super().set_parameters(*parameters)
        if len(self.parameters) == 0:
            return
        p1 = self.parameters[0]
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
        """The lower DSA bound, a value for each element.
        """
        return self._dsa_lower
    
    @dsa_lower.setter
    def dsa_lower(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_lower = value
    
    @property
    def dsa_upper(self) -> VectorParam:
        """The upper DSA bound, a value for each element.
        """
        return self._dsa_upper
    
    @dsa_upper.setter
    def dsa_upper(self, value: Value):
        if self.dsa_bounds_type == 'absolute':
            self.distribution.value_validation(self, value)
        value = self._validate_bound(value)
        self._dsa_upper = value
    
    @property
    def transform(self) -> tuple[VARIABLE_TRANSFORM, ...]:
        """The transform of each value.
        """
        return self._transform
    
    def set_transform(self, transform: VARIABLE_TRANSFORM | Sequence[VARIABLE_TRANSFORM], autosize: bool = True) -> None:
        """Set the transform of each value.

        A single transform is repeated for every value if `autosize`.

        Args:
            transform: Transform(s) of the underlying distribution to the model value: `'identity'` or `'ln'` (the model value is the exponential of the distribution).
            autosize: If true and a single transform is given for a vector variable, repeat it for every value.
        """
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
        """The central value of the variable, a vector.
        """
        return cast(VectorParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> VectorParam:
        """The values at a bound for deterministic sensitivity analysis.

        See `Variable.get_dsa_value`.

        Args:
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.
            force: Return the DSA value even if the variable is not currently selected, active and focussed for DSA.

        Returns:
            The vector of values at the requested bound.
        """
        return cast(VectorParam, super().get_dsa_value(bound, force))
    
    def get_psa_value(self) -> VectorParam:
        """The values from the last PSA draw.

        See `Variable.get_psa_value`.

        Returns:
            The vector of values.
        """
        return cast(VectorParam, super().get_psa_value())
    
    
class NumericVectorVariable(VectorVariable):
    """A variable with a vector of numeric values.

    Attributes:
        dsa_value_index: Which element is varied in DSA.
    """
    distribution: NumericVectorValuedDistribution # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_lower: NumericVectorParam # pyright: ignore[reportIncompatibleVariableOverride]
    _dsa_upper: NumericVectorParam # pyright: ignore[reportIncompatibleVariableOverride]

    dsa_value_index = 1
    """Which Value is of interest in DSA?"""

    @property
    @override
    def parameters(self) -> tuple[NumericVectorParam | MatrixNumParam, ...]:
        """The native parameters of the distribution.
        """
        return cast(tuple[NumericVectorParam, ...], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)

    @override
    def _set_native_parameters(self, parameters: ParamList) -> None:
        # Ensure that array types are recovered on deserialisation
        if not isinstance(parameters, Iterable):
            px: list[Any] = [parameters, ]
        else:
            px: list[Any] = list(parameters)
        if not isinstance(px[0], np.ndarray):
            px[0] = np.asarray(px[0])
        #nd = len(px[0])
        if len(px) > 1:
            if not isinstance(px[1], np.ndarray):
                # Assume should be square matrix
                px[1] = np.asarray(px[1])

        return super()._set_native_parameters(px)

    formatter_dp = 1
    @property
    def value_formatter(self) -> Callable[[NumericVectorParam], Sequence[str]]:        
        """
        Function for sensible formatting of the value or bound
        """
        fstring = '{:,.' + f'{self.formatter_dp:d}'+'f}'
        def formatter(seq: NumericVectorParam) -> Sequence[str]:
            return [fstring.format(x) for x in seq]
        return formatter

    @property
    def dsa_lower(self) -> NumericVectorParam:
        """The lower DSA bound, a value for each element."""
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
        """The upper DSA bound, a value for each element."""
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
        """The central value of the variable, a vector of numbers."""
        return cast(NumericVectorParam, self.get_deterministic_value())
    
    def get_dsa_value(self, bound: DSA_BOUND, force: bool = False) -> NumericVectorParam:
        """The values at a bound for deterministic sensitivity analysis.

        See `Variable.get_dsa_value`.

        Args:
            bound: Which DSA value to return: `'central'`, `'lower'` or `'upper'`.
            force: Return the DSA value even if the variable is not currently selected, active and focussed for DSA.

        Returns:
            The vector of values at the requested bound.
        """
        return cast(NumericVectorParam, super().get_dsa_value(bound, force))

    


class ConstantVariable(ScalarVariable):
    """Variable for a single value of any type that does not vary.

    The distribution is [`ConstantDistribution`][newsegsmodelframework.newsegsvariable.variable.ConstantDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = ConstantDistribution()

    @property
    @override
    def parameters(self) -> tuple[ScalarParam]:
        """The native parameters: the value.
        """
        return cast(tuple[ScalarParam], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the value. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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


class NumericConstantVariable(NumericScalarVariable):
    """Variable for a single number that does not vary.

    The distribution is [`NumericConstantDistribution`][newsegsmodelframework.newsegsvariable.variable.NumericConstantDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = NumericConstantDistribution()

    @property
    @override
    def parameters(self) -> tuple[ScalarNumParam]:
        """The native parameters: the value.
        """
        return cast(tuple[ScalarNumParam], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        return self._set_native_parameters(parameters)
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the value. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            raise NotImplementedError('Setting of raw parameters from alternative parameterisations not implemented for numeric constant variables')
        

class BinomialVariable(TwoParamNumericScalarVariable):
    """Variable for a binomially distributed count.

    The distribution is [`BinomialDistribution`][newsegsmodelframework.newsegsvariable.variable.BinomialDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = BinomialDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the expected number of successes (using the `mean` parameterisation) keeping the number of trials. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            self.raw_parameters = copy.copy(self.parameters)


class NormalVariable(TwoParamNumericScalarVariable):
    """Variable for a normally (or, with the `ln` transform, log-normally) distributed number.

    The distribution is [`NormalDistribution`][newsegsmodelframework.newsegsvariable.variable.NormalDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = NormalDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the mean (using a `mean` parameterisation); for the `ln` transform the standard deviation is re-derived from the existing sigma. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            self.raw_parameters = copy.copy(self.parameters)


class BetaVariable(TwoParamNumericScalarVariable):
    """Variable for a beta distributed proportion.

    The distribution is [`BetaDistribution`][newsegsmodelframework.newsegsvariable.variable.BetaDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = BetaDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the mean (using a `mean` parameterisation), keeping the standard deviation unless that is infeasible for the new mean. The `ln` transform is not supported. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            self.raw_parameters = copy.copy(self.parameters)


class GammaVariable(TwoParamNumericScalarVariable):
    """Variable for a gamma distributed positive number.

    The distribution is [`GammaDistribution`][newsegsmodelframework.newsegsvariable.variable.GammaDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = GammaDistribution()

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets it as the mean, using
        a parameterisation by `mean` and `sd`. The standard deviation, `sqrt(shape) * scale` of the
        current parameters, is kept, so the shape and scale change. Under a different
        parameterisation the raw parameters are then replaced by the native `(shape, scale)`.

        The `ln` transform is not supported (`NotImplementedError`). Does nothing if the model value
        is already the deterministic value, or the model is of the wrong type for the variable.
        The spread of the distribution is not recoverable from a single model value, so this is
        best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            sd = np.sqrt(shape * scale**2)
        else:
            raise NotImplementedError('Derivation of log-gamma parameters not supported')
        
        self.set_parameters(model_val, sd)

        if not (current_p_index == new_p_index):
            self.parameterisation_index = current_p_index
            # If we are here, this means the variable is set to shape, scale form
            # and so we should over-write the raw parameters so they can be read to the
            # interface
            self.raw_parameters = copy.copy(self.parameters)


class ConstantVectorVariable(VectorVariable):
    """Variable for a vector of values that do not vary.

    The distribution is [`ConstantVectorDistribution`][newsegsmodelframework.newsegsvariable.variable.ConstantVectorDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = ConstantVectorDistribution()
    
    @property
    def parameters(self) -> tuple[VectorParam]:
        """The native parameters: the vector of values.
        """
        return cast(tuple[VectorParam], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        self._set_native_parameters(parameters)

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the vector of values. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
    """Variable for a multivariate normal (optionally log-normal) vector.

    The distribution is [`MultivariateNormalDistribution`][newsegsmodelframework.newsegsvariable.variable.MultivariateNormalDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = MultivariateNormalDistribution()

    @property
    def parameters(self) -> tuple[NumericVectorParam, MatrixNumParam]:
        """The native parameters: the vector of means and the variance-covariance matrix.
        """
        return cast(
            tuple[NumericVectorParam, MatrixNumParam],
            self._get_native_parameters()
        )

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        self._set_native_parameters(parameters)
    
    
    def set_parameters(self, *parameters: Param):
        """Set the parameters from raw parameters.

        If the parameterisation takes a `transform`, the transform of the variable is supplied.

        Args:
            *parameters: The parameters, in native form.
        """
        if 'transform' in self.parameterisation.names and len(parameters) < 3:
            super().set_parameters(*parameters, self.transform)
        else:
            super().set_parameters(*parameters)

    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the mean vector, re-deriving the spread from the existing parameters. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
            self.raw_parameters = copy.copy(self.parameters)


class DirichletVariable(NumericVectorVariable):
    """Variable for a vector of probabilities summing to 1.

    The distribution is [`DirichletDistribution`][newsegsmodelframework.newsegsvariable.variable.DirichletDistribution], and the variable is created with `Variable(name, distribution = ...)`.
    """
    distribution = DirichletDistribution()

    @property
    def parameters(self) -> tuple[NumericVectorParam]:
        """The native parameters: the vector of concentration parameters.
        """
        return cast(tuple[NumericVectorParam], self._get_native_parameters())

    @parameters.setter
    def parameters(self, parameters: ParamList) -> None:
        self._set_native_parameters(parameters)
    
    def synchronise_from_model(
        self, 
        model: ModelType
    ) -> None:
        """Set the parameters of the variable from the present value in the model.

        Reads the model value (`model_section`, `model_parameter`) and sets the concentration parameters (`alpha`) to the model values, so the variances are whatever those imply. Does nothing if the model value is already the deterministic value, or the model is of the wrong type for the variable. The spread of the distribution is not recoverable from a single model value, so this is best avoided.

        Args:
            model: The energy model or finance model.
        """
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
    'NumericConstantVariable': partial(Variable, distribution = 'numeric_constant'),
    'BinomialVariable': partial(Variable, distribution = 'binomial'),
    'NormalVariable': partial(Variable, distribution = 'normal'),
    'BetaVariable': partial(Variable, distribution = 'beta'),
    'GammaVariable': partial(Variable, distribution = 'gamma'),
    'ConstantVectorVariable': partial(Variable, distribution = 'constant_vector'),
    'MultivariateNormalVariable': partial(Variable, distribution = 'mvn'),
    'DirichletVariable': partial(Variable, distribution = 'dirichlet'),
}
"""Constructors of each class of variable, by class name; used to restore a variable from its serialised state.
"""

def variable_from_dict(config: dict[str, Any]) -> Variable:
    """Create a variable from a dictionary of its serialised state.

    The dictionary names the `class` of variable.

    Args:
        config: Dictionary of the serialised state.

    Returns:
        The variable.
    """
    classname = config.get('class')
    if classname is None:
        raise ValueError(f'`class` not found in configuration dictionary with keys {config.keys()}')
    constructor = VARIABLE_CONSTRUCTORS.get(classname)
    if constructor is None:
        raise ValueError(f'Constructor not found for {classname}')
    var = constructor('Placeholder')
    var.update(config)

    # The update will have messed with the revision number, so reset that
    revis = config.get('_config', {}).get('_revision')
    if revis is not None:
        var.revision = revis
    
    return var

def variable_uid(variable: Variable) -> str | list[str]:
    """The varid of a variable.

    The varid is `{interface_section}.{interface_key}.{interface_subindex}`. It identifies the variable in the interface and in metamodels.

    Args:
        variable: The variable.

    Returns:
        The varid.
    """
    if not isinstance(variable.interface_key, str) and isinstance(variable.interface_key, Sequence):
        sub = variable.interface_subindex
        if isinstance(variable.interface_section, str):
            return [f"{variable.interface_section}.{key}.{sub}" for key in variable.interface_key]
        else:
            return [f"{section}.{key}.{sub}" for key, section in zip(variable.interface_key, variable.interface_section)]
    else:
        return str(variable.interface_section) + "." + str(variable.interface_key) + "." + str(variable.interface_subindex)

def variable_uid_to_dict(varid: str):
    """Split a varid into its parts.

    Args:
        varid: Variable id of the form `{section}.{key}.{subindex}`.

    Returns:
        Dictionary of `interface_section`, `interface_key` and `interface_subindex`.
    """
    ss = varid.split('.')
    if not len(ss) == 3:
        raise ValueError(f'{varid} is not a valid variable id')
    return dict(
        interface_section = ss[0],
        interface_key = ss[1],
        interface_subindex = ss[2],
    )