# Finance Model API Reference

### NewsegsFinance

A `NewsegsFinance` implements and extends the [NewsegsFinanceInterface](core.md#newsegsfinanceinterface).

#### Implementation

```mermaid
---
  config:
    class:
      hideEmptyMembersBox: true
---
classDiagram
    direction TB
    class NewsegsFinance {
        +NewsegsModelInterface model
        +float benefit_discount_rate
        +float cost_discount_rate
        ...
    }
    NewsegsFinanceInterface <|-- NewsegsFinance
    NewsegsFinance o-- "1" NewsegsModelInterface
    RunnableNewsegsComponent <|-- NewsegsFinanceInterface
    SerialiseToDictMixin <|-- NewsegsComponent
    NewsegsComponent <|-- RunnableNewsegsComponent
    RunnableNewsegsComponent <|-- NewsegsModelInterface
```

::: newsegsmodelframework.newsegsfinance
    options:
        show_submodules: true
