# Application database

The `Dash` app is dependent upon an SQlite database for storing configurations.

```{mermaid}
---
config:
  layout: elk
---
erDiagram
    SNAPSHOT {
        int snapshot_id PK
        int project_id FK
        str label
        DateTime timestamp
    }

    VARIABLE_CONFIG {
        int variable_config_id PK
        str module_type
        str payload
        str label
        bool retain
    }

    SNAPSHOT_VARIABLE_CONFIG {
        int snapshot_id PK, FK
        int variable_config_id PK
        etc etc
    }

    MODULE_CONFIG {
        int module_config_id PK
        str module_type
        str module_class
        str module_version
        str config_payload
        int revision
        int last_result_id
        str label
        bool retain
    }

    SNAPSHOT_MODULE_CONFIG {
        int snapshot_id PK, FK
        int module_config_id PK
        etc etc
    }

    DEFAULT_MODULE_CONFIG {
        int default_module_config_id
        str module_type
        str module_class
        str module_verson
        str config_payload
        str label
        bool retain
    }

    MODULE_VARIABLE {
        int module_config_id PK, FK
        int variable_config_id PK, FK
    }

    SNAPSHOT_MODULE_VARIABLE {
        int snapshot_id PK, FK
        int module_config_id PK, FK
        int variable_config_id PK, FK
    }

    VARIABLE_CONFIG ||--o{ MODULE_VARIABLE : "informs modules"
    MODULE_CONFIG ||--o{ MODULE_VARIABLE : "has variables"
    DEFAULT_MODULE_CONFIG }|--o| MODULE_CONFIG : "may overwrite where (module_type, module_class) and compatible module_version"

    SNAPSHOT_VARIABLE_CONFIG ||--o{ SNAPSHOT_MODULE_VARIABLE : "informs modules where (snapshot_id, variable_config_id)"
    SNAPSHOT_MODULE_CONFIG ||--o{ SNAPSHOT_MODULE_VARIABLE : "has variables where (snapshot_id, module_config_id)"
    
    RESULT {
        int result_id PK
        int module_config_id FK
        int run_id
        str module_type
        str module_class
        str module_version
        int module_config_revision
        str result_type
        str result_file
        bool retain
    }

    SNAPSHOT_RESULT {
        int snapshot_id PK, FK
        int result_id PK
        int module_config_id FK
        etc etc
    }

    MODULE_CONFIG ||--o{ RESULT : "has"
    
    SNAPSHOT_MODULE_CONFIG ||--o{ SNAPSHOT_RESULT : "has where (snapshot_id, module_config_id)"


    EM_CONFIG {
        int em_config_id PK
        int grid_config_id FK
        int generation_config_id FK
        int cs_config_id FK
        int table_config_id FK
        str model_class
        str model_version
        str config_payload
        int revision
        str label
        bool retain
    }

    SNAPSHOT_EM_CONFIG {
        int snapshot_id PK, FK
        int em_config_id PK
        int grid_config_id FK
        int generation_config_id FK
        int cs_config_id FK
        int table_config_id FK
        etc etc
    }

    EM_CONFIG ||--|{ MODULE_CONFIG : "has"

    SNAPSHOT_EM_CONFIG ||--|{ SNAPSHOT_MODULE_CONFIG : "has where (snapshot_id, module_config_id)"


    FM_CONFIG {
        int fm_config_id PK
        int financedata_config_id FK
        int table_config_id FK
        str model_class
        str model_version
        str config_payload
        int revision
        str label
        bool retain
    }

    SNAPSHOT_FM_CONFIG {
        int snapshot_id PK, FK
        int fm_config PK
        int financedata_config_id FK
        int table_config_id FK
        etc etc
    }

    FM_CONFIG ||--|{ MODULE_CONFIG : "has"

    SNAPSHOT_FM_CONFIG ||--|{ SNAPSHOT_MODULE_CONFIG : "has where (snapshot_id, module_config_id)"


    METAMODEL {
        int metamodel_id PK
        int em_config_id FK
        int fm_config_id FK
        int table_config_id FK
        int revision
        str label
        bool retain
        float lat
        float lon
        float n_units
    }

    SNAPSHOT_METAMODEL {
        int snapshot_id PK, FK
        int metamodel_id PK
        int em_config_id FK
        int fm_config_id FK
        int table_config_id FK
        etc etc
    }

    METAMODEL ||--|| EM_CONFIG : "has"
    METAMODEL ||--|| FM_CONFIG : "has"
    METAMODEL ||--|| MODULE_CONFIG : "has"

    SNAPSHOT_METAMODEL ||--|| SNAPSHOT_EM_CONFIG : "has where (snapshot_id, em_config_id)"
    SNAPSHOT_METAMODEL ||--|| SNAPSHOT_FM_CONFIG : "has where (snapshot_id, fm_config_id)"
    SNAPSHOT_METAMODEL ||--|| SNAPSHOT_MODULE_CONFIG : "has where (snapshot_id, module_config_id)"

    PROJECT {
        int project_id PK
        int read_group_id FK
        int write_group_id FK
        int dsa_module_config_id FK
        int psa_module_config_id FK
        int table_config_id FK
        str model_type
        str model_version
        str label
        bool retain
    }

    SNAPSHOT_PROJECT {
        int snapshot_id PK, FK
        int project_id PK
        int dsa_module_config_id FK
        int psa_module_config_id FK
        int table_config_id FK
        etc etc
    }

    PROJECT ||--|{ MODULE_CONFIG : "has"

    SNAPSHOT_PROJECT ||--|{ SNAPSHOT_MODULE_CONFIG : "has where (snapshot_id, module_config_id)"

    SNAPSHOT ||--|| SNAPSHOT_PROJECT : "has"


    PROJECT_METAMODEL {
        int project_id PK, FK
        int metamodel_id PK, FK
    }

    SNAPSHOT_PROJECT_METAMODEL {
        int snapshot_id PK, FK
        int project_id PK
        int metamodel_id PK
    }


    PROJECT ||--o{ PROJECT_METAMODEL : "contains"
    PROJECT_METAMODEL }o--|| METAMODEL : "belongs to"

    SNAPSHOT_PROJECT ||--o{ SNAPSHOT_PROJECT_METAMODEL : "contains where (snapshot_id, project_id)"
    SNAPSHOT_PROJECT_METAMODEL }o--|| SNAPSHOT_METAMODEL : "belongs to where (snapshot_id, metamodel_id)"

    PROJECT ||--o{ SNAPSHOT : "generates"
    
    
    RUN {
        int run_id PK
        int project_id FK
        str request_id
        str request_type
        str request_payload
        str status
        datetime last_updated
        float progress
        str progress_message
        bool cancel_requested
    }

    RUN ||--o{ RESULT : "produces"
    PROJECT ||--o{ RUN : "requests"


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

```