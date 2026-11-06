# Energy Model API Reference

### NewsegsModel

A `NewsegsModel` implements and extends the [NewsegsModelInterface](core.md#newsegsmodelinterface). It manages three [NewsegsModule](core.md#newsegsmodule)s - the Grid, the Generation, and the Consumption / Storage module. 

#### Implementation

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction LR
    class NewsegsModel {
        +NewsegsGrid grid*
        +NewsegsGeneration generation*
        +NewsegsCS consumption_storage*
        +Location location*
        +bool dirty

        +set_run_period(TimeSpan timespan)*
        +get_run_period() TimeSpan*

    }
    class NewsegsGeneration {
        +Location location*
    }
    class NewsegsCS {
        +Location location*
    }
    NewsegsModelInterface <|-- NewsegsModel
    NewsegsModel *-- "1" NewsegsGrid
    NewsegsModel *-- "1" NewsegsGeneration
    NewsegsModel *-- "1" NewsegsCS
    NewsegsModel --> TimeSpan
    NewsegsModel --> Location
    NewsegsGeneration --> Location
    NewsegsCS --> Location
    NewsegsComponent <|-- NewsegsModule 
    NewsegsModule <|-- NewsegsGrid
    NewsegsModule <|-- NewsegsGeneration
    NewsegsModule <|-- NewsegsCS
    NewsegsModule ..> NewsegsModelInterface
    EnvironmentServerInterface <|-- NewsegsModelInterface
    ResultsServerInterface <| -- NewsegsModelInterface
    NewsegsModelTimeInterface <|-- NewsegsModelInterface
    RunnableNewsegsComponent <|-- NewsegsModelInterface
    SerialiseToDictMixin <|-- NewsegsComponent
    NewsegsComponent <|-- RunnableNewsegsComponent
    NewsegsModule ..> NewsegsModuleResult
    SerialiseToDictMixin <|-- TimeSpan
    SerialiseToDictMixin <|-- Location
```

::: newsegsmodelframework.newsegsmodel
    options:
        show_submodules: true
