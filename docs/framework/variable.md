# Variable API Reference

### Variable

A Variable is a container for data associated with an Energy Model or Finance Model parameter. Principally, they exist to hold data related to sensitivity analysis of a Metamodel i.e. whilst the Model and Finance hold current parameters for analysis, the Variables list holds the metaparameters which indicate how those parameters are to be varied in Deterministic (One-Way) Sensitivity Analysis and Probabilistic Sensitivity Analysis.

> Glossary:
> - Parameter: An item of data which influences the outcome(s) of a model (e.g. fixed cost per kW wind generation installed).
> - Value: A number, string, or vector of numbers or strings which can be used as a Parameter of a Model or Finance (e.g. £1,000 / kW).
> - Variable: A container holding data allowing for the production of Values used to parameterise a Model (e.g. an object identifying itself as associated with the parameter "fixed per-unit cost of wind" within an Energy Model, where that parameter is uncertain with a probability density described by a Gamma distribution with mean £1,000 / kW and standard deviation of £100 / kW).
> - Metaparameter: An item of data used to parameterise a Variable (e.g. the standard deviation of the fixed per-unit cost of wind).
> - Metavalue: A number, string, or vector of number or strings which can be used as a Metaparameter of a Variable (e.g. £100 / kW).

 The data a Variable carries serves the following purposes:

1. Naming and presenting the Variable (i.e. a `name`, a `unit`, an `icon_name`).
1. Hierarchically identifying the associated parameter for presentation in a User Interface:
    - `configuration_type`: `'model'` or `'finance'`
    - `interface_section`: e.g. `'gen_input'` for generation configuration input
    - `interface_key`: e.g. `'pv_capacity'` for the value in kWp of PV installed
    - `interface_subindex`: e.g. `0` to indicate this is the value for the 0-indexed PV array aspect, which might be 180° (south) whilst index `1` might be an array at 90° (east).
1. Hierarchically identifying the associated parameter within the Model or Finance object:
    - `configuration_type`: `'model'` or `'finance'` (shared with the Interface purpose)
    - `model_section`: e.g. `'mod_gen'` for the generation Module of a Model.
    - `model_parameter`: e.g. `'pv_capacity'` for the value in kWp of PV installed.
1. Identifying the statistical distribution used for its Value(s).
1. Storing Metaparameters to provide a fixed (deterministic / mean values) Value to its associated Parameter.
1. Storing Metaparameters for use in DSA (i.e. whether the Parameter is to be varied, and the values to which to set the associated Parameter).
1. Storing Metaparameters for use in PSA (i.e. whether the Parameter is to be varied, and the distribution characteristics of the Parameter).

#### Parameterisation

A Parameterisation is a way of describing a Distribution; a single Distribution may have multiple Parameterisations. Parameterisations convert Parameters into canonical form for use by a Distribution using `generator` functions.

#### Implementation

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction TD
    class Singleton
    class Parameterisation {
        +tuple[str, ...] names
        +tuple[str, ...] types
        +tuple[Param, ...] defaults
        +generator(*args, **kwargs) tuple[Param, ...]*
        +partial_generator(...) tuple[tuple[Param, ...],tuple[Param, ...]]*
        +eligibility(Variable var) bool$
    }
    Singleton <|-- Parameterisation
    class TwoParamParameterisation {
        +generator(*args, **kwargs) tuple[ScalarNumParam, ScalarNumParam]*
        +partial_generator(...) tuple[tuple[ScalarNumParam, ScalarNumParam],tuple[ScalarNumParam, ScalarNumParam]]*
    }
    Parameterisation <|-- TwoParamParameterisation
    class VectorParameterisation {
        +generator(*args, **kwargs) tuple[MatrixNumParam, ...]*
        +partial_generator(...) tuple[tuple[MatrixNumParam, ...], tuple[MatrixNumParam, ...]]*
    }
    Parameterisation <|-- VectorParameterisation
```
*Parameterisation UML Diagram*

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction TD
    class Distribution {
        +str distribution
        +tuple[Parameterisation] parameterisations
        +bool dsa_possible
        +bool psa_possible
        +bool optim_possible
        +tuple[str] permitted_dsa_bounds
        +n_values(Variable var) int$
        +parameter_validation(Variable var)*
        +value_validation(Variable var, Value *values)*
        +deterministic_value(Variable var) Value*
        +std(Variable var) Value*
        +interval(Variable var, float confidence) tuple[Value, Value]*
        +dsa_value(Variable var, str bound) Value*
        +psa_value(Variable var, np.random.Generator rng) Value*
    }
    class ScalarValuedDistribution {
        +deterministic_value(Variable var) ScalarParam*
        +std(Variable var) ScalarParam*
        +interval(Variable var, float confidence) tuple[ScalarParam, ScalarParam]*
        +dsa_value(Variable var, str bound) ScalarParam*
        +psa_value(Variable var, np.random.Generator rng) ScalarParam*
    }
    class NumericScalarValuedDistribution {
        +deterministic_value(Variable var) ScalarNumParam*
        +std(Variable var) ScalarNumParam*
        +interval(Variable var, float confidence) tuple[ScalarNumParam, ScalarNumParam]*
        +dsa_value(Variable var, str bound) ScalarNumParam*
        +psa_value(Variable var, np.random.Generator rng) ScalarNumParam*
    }
    class VectorValuedDistribution {
        +deterministic_value(Variable var) VectorParam*
        +std(Variable var) VectorParam*
        +interval(Variable var, float confidence) tuple[VectorParam, VectorParam]*
        +dsa_value(Variable var, str bound) VectorParam*
        +psa_value(Variable var, np.random.Generator rng) VectorParam*
    }
    class NumericVectorValuedDistribution {
        +deterministic_value(Variable var) NumericVectorParam*
        +std(Variable var) NumericVectorParam*
        +interval(Variable var, float confidence) tuple[NumericVectorParam, NumericVectorParam]*
        +dsa_value(Variable var, str bound) NumericVectorParam*
        +psa_value(Variable var, np.random.Generator rng) NumericVectorParam*
    }
    Singleton <|-- Distribution
    Singleton <|-- Parameterisation
    Distribution o-- Parameterisation
    Distribution <|-- ScalarValuedDistribution
    ScalarValuedDistribution <|-- NumericScalarValuedDistribution
    NumericScalarValuedDistribution <|-- TwoParamNumericScalarValuedDistribution
    Distribution <|-- VectorValuedDistribution
    VectorValuedDistribution <|-- NumericVectorValuedDistribution

    Distribution ..> Variable
```
*Distribution UML Diagram*

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction LR

    Parameterisation <|-- TwoParamParameterisation

    Distribution <|-- ScalarValuedDistribution
    ScalarValuedDistribution <|-- NumericScalarValuedDistribution
    NumericScalarValuedDistribution <|-- TwoParamNumericScalarValuedDistribution
    Distribution <|-- VectorValuedDistribution
    VectorValuedDistribution <|-- NumericVectorValuedDistribution

    Parameterisation <|-- _ConstantParameterisation
    ScalarValuedDistribution <|.. ConstantDistribution
    ConstantDistribution o-- _ConstantParameterisation

    Parameterisation <|-- _NumericConstantParameterisation
    NumericScalarValuedDistribution <|.. NumericConstantDistribution
    NumericConstantDistribution o-- _NumericConstantParameterisation

    TwoParamParameterisation <|-- _BinomialParameterisation
    TwoParamNumericScalarValuedDistribution <|.. BinomialDistribution
    BinomialDistribution o-- _BinomialParameterisation

    TwoParamParameterisation <|-- _NormalParameterisation
    TwoParamNumericScalarValuedDistribution <|.. NormalDistribution
    NormalDistribution o-- _NormalParameterisation

    TwoParamParameterisation <|-- _BetaParameterisation
    TwoParamNumericScalarValuedDistribution <|.. BetaDistribution
    BetaDistribution o-- _BetaParameterisation

    TwoParamParameterisation <|-- _GammaParameterisation
    TwoParamNumericScalarValuedDistribution <|.. GammaDistribution
    GammaDistribution o-- _GammaParameterisation

    VectorParameterisation <|-- _ConstantVectorParameterisation
    VectorValuedDistribution <|.. ConstantVectorDistribution
    ConstantVectorDistribution o-- _ConstantVectorParameterisation

    VectorParameterisation <|-- _MultivariateNormalParameterisation
    NumericVectorValuedDistribution <|.. MultivariateNormalDistribution
    MultivariateNormalDistribution o-- _MultivariateNormalParameterisation

    Parameterisation <|-- _DirichletParameterisation
    NumericVectorValuedDistribution <|.. DirichletDistribution
    DirichletDistribution o-- _DirichletParameterisation
```
*Concrete Distribution classes - UML diagram*

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction TD
    NewsegsComponent <|-- Variable
    Variable o-- "1" Distribution
    class Variable {
        +Distribution distribution
        +int parameterisation_index
        +str name
        +str label
        +str unit
        +str icon_name
        +str configuration_type
        +str model_section
        +str model_parameter
        ...
        +get_deterministic_value() Value
        +get_std() Value
        +get_confidence_interval(float confidence) tuple[Value, Value]
        +reset_parameters()
        +get_dsa_value(str bound, bool force) Value
        +draw_psa(np.random.Generator rng, int retries) Value
        +get_psa_value() Value
        +update_model_deterministic(ModelType model)
        +update_model_dsa(ModelType model, str bound)
        +update_model_psa(ModelType model)
        +synchronise_from_model(ModelType model)*
    }
    class ScalarVariable {
        +get_deterministic_value() ScalarParam
        +get_std() ScalarParam
        +get_dsa_value(str bound, bool force) ScalarParam
        +draw_psa(np.random.Generator rng, int retries) ScalarParam
        +get_psa_value() ScalarParam
    }
    class NumericScalarVariable {
        +get_deterministic_value() ScalarNumParam
        +get_std() ScalarNumParam
        +get_dsa_value(str bound, bool force) ScalarNumParam
        +draw_psa(np.random.Generator rng, int retries) ScalarNumParam
        +get_psa_value() ScalarNumParam
    }
    class VectorVariable {
        +get_deterministic_value() VectorParam
        +get_std() VectorParam
        +get_dsa_value(str bound, bool force) VectorParam
        +draw_psa(np.random.Generator rng, int retries) VectorParam
        +get_psa_value() VectorParam
    }
    class NumericVectorVariable {
        +get_deterministic_value() NumericVectorParam
        +get_std() NumericVectorParam
        +get_dsa_value(str bound, bool force) NumericVectorParam
        +draw_psa(np.random.Generator rng, int retries) NumericVectorParam
        +get_psa_value() NumericVectorParam
    }

    Variable <|-- ScalarVariable
    ScalarVariable <|-- NumericScalarVariable
    NumericScalarVariable <|-- TwoParamNumericScalarVariable
    Variable <|-- VectorVariable
    VectorVariable <|-- NumericVectorVariable
    Variable ..> ModelType
    NewsegsModel o-- ModelType
    NewsegsFinance o-- ModelType 
```
*Variable UML Diagram*

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction LR

    ScalarVariable <|.. ConstantVariable
    ConstantVariable *-- "1" ConstantDistribution

    NumericScalarVariable <|.. NumericConstantVariable
    NumericConstantVariable *-- "1" NumericConstantDistribution

    TwoParamNumericScalarVariable <|.. BinomialVariable
    BinomialVariable *-- "1" BinomialDistribution

    TwoParamNumericScalarVariable <|.. NormalVariable
    NormalVariable *-- "1" NormalDistribution

    TwoParamNumericScalarVariable <|.. BetaVariable
    BetaVariable *-- "1" BetaDistribution

    TwoParamNumericScalarVariable <|.. GammaVariable
    GammaVariable  *-- "1" GammaDistribution

    VectorVariable <|.. ConstantVectorVariable
    ConstantVectorVariable  *-- "1" ConstantVectorDistribution

    NumericVectorVariable <|.. MultivariateNormalVariable
    MultivariateNormalVariable *-- "1" MultivariateNormalDistribution

    NumericVectorVariable <|.. DirichletVariable
    DirichletVariable *-- "1" DirichletDistribution

    Variable <|-- ScalarVariable
    ScalarVariable <|-- NumericScalarVariable
    NumericScalarVariable <|-- TwoParamNumericScalarVariable
    Variable <|-- VectorVariable
    VectorVariable <|-- NumericVectorVariable
```
*Concrete Variable classes - UML diagram*

::: newsegsmodelframework.newsegsvariable
    options:
        show_submodules: true
