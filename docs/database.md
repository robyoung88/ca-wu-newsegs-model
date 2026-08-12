# Application database

The `Dash` app is dependent upon an SQlite database for storing configurations.

```{mermaid}
---
config:
  layout: elk
---
erDiagram
    PROJECT ||--o{ PROJECT_METAMODEL : "contains"
    PROJECT_METAMODEL }o--|| METAMODEL : "belongs to"
    METAMODEL ||--|| MODEL_CONFIG : contains
    METAMODEL ||--|| FINANCE_CONFIG : contains
    METAMODEL ||--o{ RESULT : contains
    MODEL_CONFIG ||--o{ MODULE_CONFIG : contains
    FINANCE_CONFIG ||--|| MODULE_CONFIG : contains
    
    PROJECT {
        int project_id PK
        int read_group_id FK
        int write_group_id FK
        str label
        bool retain
    }
    PROJECT_METAMODEL {
        int project_id PK, FK
        int metamodel_id PK, FK
    }
    METAMODEL {
        int metamodel_id PK
        int model_config_id
        int finance_config_id
        str label
        bool retain
        float lat
        float lon
        float n_units
    }
    MODEL_CONFIG {
        int model_config_id PK
        str model_class
        int grid_config_id
        int generation_config_id
        int cs_config_id
        str label
        bool retain
    }
    FINANCE_CONFIG {
        int finance_config_id PK
        str finance_class
        int financedata_config_id
        str label
        bool retain
    }
    
    MODULE_CONFIG {
        int module_config_id PK
        str module_type
        str module_class
        str config_payload
        int revision
        int last_result_id
        str label
        bool retain
    }
    VARIABLE_CONFIG {
        int variable_config_id PK
        str module_type
        str payload
        str label
        bool retain
    }
    MODULE_VARIABLES {
        int module_config_id PK, FK
        int variable_config_id PK, FK
    }
    MODULE_CONFIG ||--o{ MODULE_VARIABLES : "has variables"
    VARIABLE_CONFIG ||--o{ MODULE_VARIABLES : "informs"
    
    DEFAULT_MODULE_CONFIG {
        int default_module_config_id
        str module_type
        str module_class
        str config_payload
        str label
        bool retain
    }

    USER {
        int user_id PK
        string email
        string name
    }
    GROUP {
        int group_id PK
        string name
        string description
    }
    MEMBERSHIP {
        int user_id PK, FK
        int group_id PK, FK
        string role
    }

    USER ||--o{ MEMBERSHIP : "belongs to"
    GROUP ||--o{ MEMBERSHIP : "has members"
    GROUP ||--o{ PROJECT : "grants read access"
    GROUP ||--o{ PROJECT : "grants write access"

    RUN {
        int run_id PK
        int project_id FK
        int request_id
        str request_payload
        str status
        datetime last_updated
        float progress
        str progress_message
        bool cancel_requested
    }
    RESULT {
        int result_id PK
        int run_id FK
        int module_config_id
        int revision
        str result_type
        str result_file
    }
    RUN ||--o{ RESULT : "produces"
    PROJECT ||--o{ RUN : "requests"

```