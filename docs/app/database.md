# Application database

The `newsegsmodelapp` Dash app stores configurations, results metadata, job requests and
sessions in a SQLite database. The tables are defined with SQLAlchemy in
`newsegsmodelapp.backend.db.db_tables` and migrated with Alembic (`alembic/versions`).

Large result payloads are not stored in the database: the `results` table records the
`result_file` in the results store, and the database holds only the metadata needed to find it.

## Live tables

Identifiers for variables and components are text (`prefix + uuid`), not integers. The
`component_configs` table holds the configuration of every individual model module (grid,
generation, consumption/storage, tables...). The `em_configs`, `fm_configs`, `metamodels` and
`projects` tables compose these into the structure described in
[Metamodel](../framework/metamodel.md).

```mermaid
erDiagram
    PROJECTS {
        string id PK
        string dsa_component_config_id FK
        string psa_component_config_id FK
        string table_config_id FK
        string focussed_metamodel_id FK
        string model_type
        string model_version
        string payload
        int revision
        string label
        bool retain
        datetime created_at
        datetime modified_at
        string modified_order
    }

    METAMODELS {
        string id PK
        string em_config_id FK
        string fm_config_id FK
        string table_config_id FK
        string optim_config_id FK
        string payload
        int revision
        string label
        bool retain
        string location
        float lat
        float lon
        float n_units
    }

    EM_CONFIGS {
        string id PK
        string grid_config_id FK
        string generation_config_id FK
        string cs_config_id FK
        string modeldata_config_id FK
        string table_config_id FK
        string model_class
        string model_version
        string model_type
        string payload
        int revision
        string label
        bool retain
    }

    FM_CONFIGS {
        string id PK
        string financedata_config_id FK
        string table_config_id FK
        string model_class
        string model_version
        string payload
        int revision
        string label
        bool retain
    }

    COMPONENT_CONFIGS {
        string id PK
        string component_type
        string component_class
        string component_version
        string payload
        int revision
        int last_result_id
        string label
        bool retain
    }

    VARIABLE_CONFIGS {
        string id PK
        string varid
        string interface_section
        string interface_key
        int interface_subindex
        int revision
        string component_version
        string component_type
        string variable_type
        string distribution
        int parameterisation_index
        string raw_parameter_0
        string raw_parameter_1
        string last_deterministic_value
        bool dsa_show
        bool dsa_selectable
        bool dsa_selected
        string dsa_bounds_type
        string dsa_lower
        string dsa_upper
        string dsa_value_lower
        string dsa_value_upper
        bool psa_show
        bool psa_selectable
        bool psa_selected
        string last_std
        string psa_ci_lower
        string psa_ci_upper
        bool optim_show
        bool optim_selectable
        bool optim_selected
        string optim_min
        string optim_max
        int optim_plot_intervals
        string payload
        string label
        string icon_name
        string unit
        float interface_min
        float interface_max
        float interface_step
        int formatter_dp
        bool retain
    }

    PROJECT_METAMODELS {
        string project_id PK, FK
        string metamodel_id PK, FK
        datetime created_at
        string created_order
    }

    PROJECT_VARIABLES {
        string project_id PK, FK
        string variable_config_id PK, FK
    }

    METAMODEL_VARIABLES {
        string metamodel_id PK, FK
        string variable_config_id PK, FK
        int key_order
    }

    RESULTS {
        int result_id PK
        string component_config_id FK
        int request_id
        int run_id
        string component_type
        string component_class
        string component_version
        int component_config_revision
        string result_type
        string result_file
        bool retain
        datetime created_at
    }

    REQUESTS {
        int request_id PK
        string project_id FK
        string request_type
        string request_class
        string request_label
        int trigger_request_id
        string trigger_request_type
        int run_id
        string model_type
        string payload
        string status
        bool background_procedure
        int retry_number
        int max_retries
    }

    RUNS {
        int run_id PK
        int request_id FK
        string status
        float progress
        string progress_message
        bool cancel_requested
        datetime created_at
        datetime modified_at
    }

    SESSIONS {
        string session_id PK
        string active_project_id FK
    }

    PROCESS_STALENESS {
        string metamodel_id PK
        string process PK
        bigint inputs_changed_ns
        bigint last_run_ns
    }

    PROJECTS ||--o{ PROJECT_METAMODELS : "contains"
    METAMODELS ||--o{ PROJECT_METAMODELS : "belongs to"
    PROJECTS ||--o{ PROJECT_VARIABLES : "has default variables"
    VARIABLE_CONFIGS ||--o{ PROJECT_VARIABLES : "informs"
    METAMODELS ||--o{ METAMODEL_VARIABLES : "has variables"
    VARIABLE_CONFIGS ||--o{ METAMODEL_VARIABLES : "informs"
    PROJECTS }o--o| METAMODELS : "focusses"

    METAMODELS }o--|| EM_CONFIGS : "uses"
    METAMODELS }o--|| FM_CONFIGS : "uses"

    PROJECTS }o--o| COMPONENT_CONFIGS : "DSA, PSA and table configs"
    METAMODELS }o--o| COMPONENT_CONFIGS : "table and optimisation configs"
    EM_CONFIGS }o--o| COMPONENT_CONFIGS : "grid, generation, cs, modeldata, table configs"
    FM_CONFIGS }o--o| COMPONENT_CONFIGS : "financedata and table configs"

    COMPONENT_CONFIGS ||--o{ RESULTS : "produces"
    PROJECTS ||--o{ REQUESTS : "requests"
    REQUESTS ||--o{ RUNS : "executed by"
    RUNS |o..o{ RESULTS : "produces (no FK)"
    PROJECTS ||--o{ SESSIONS : "active in"
    METAMODELS |o..o{ PROCESS_STALENESS : "tracked per process (no FK)"
```

### Notes

* Dotted lines are relationships without a foreign key.
* `metamodel_variables.key_order` is the position of the variable's key (`{section}.{key}`, without the subindex)
  among the metamodel's variables, so that they are loaded in the order they were saved. It is null for rows saved
  before it was recorded, whose order is taken from the metamodel's payload.
* `variable_configs` holds the settings of a variable for each analysis in columns of their own (`dsa_*`, `psa_*`,
  `optim_*`), with its parameterisation (`parameterisation_index`, `raw_parameter_*`), the limits and formatting of
  its input (`interface_*`, `formatter_dp`, `unit`, `icon_name`), and the full variable in `payload`.
* `process_staleness` has no foreign key, so that deleting a metamodel is never blocked by its
  staleness rows. It records, per metamodel and per process (see `db_staleness.PROCESSES`), when
  the inputs relevant to the process last changed and when the last completed run began. A
  process is stale when its inputs changed after its last run started.
* `metamodels.optim_config_id` is the `OptimComponent` holding the method and statistic of
  optimisation. It is null for metamodels saved before it existed; they are given the default
  component when loaded. The bounds of optimisation are held by each variable, in the
  `optim_min`, `optim_max` and `optim_plot_intervals` columns of `variable_configs`.
* `variable_configs.component_version` is the version of the `Variable` class that saved the
  row, null if it was saved before versions were recorded. As with the other components, the
  payload records the version too, and a payload newer than the app supports is rejected.
* The times of `runs` are in UTC, without a timezone: `created_at` is filled in by SQLite, and `modified_at` by the
  app (`db_tables.utc_now`). The dispatcher marks a run as failed once `modified_at` is older than
  `DEAD_CALCULATION_INTERVAL_SECONDS`, and pruning compares both with a cutoff in UTC, so both work whatever the host's
  timezone. `projects.modified_at` is still in local time.
* `requests` are created by the front end (from the actions in the app) and picked up by the
  dispatcher; each request is executed as one or more `runs` by a worker. The run carries the
  progress and cancellation flag that the front end polls.
* `results.request_id` and `results.run_id` are for convenience and are deliberately not foreign
  keys.
* Users, groups and read/write access to projects are planned (see the `TODO` in
  `db_tables.projects`) but are not yet implemented.

## Snapshot tables

A snapshot freezes a copy of a project - its metamodels, models, components, variables and
results - so that it can be restored later. Each live table `x` has a `snapshot_x` twin
whose primary key is extended with `snapshot_id`, and whose remaining columns are cloned from
the live table (without its foreign keys). Foreign keys between snapshot tables are composite,
so they refer to the rows *within the same snapshot*.

```mermaid
erDiagram
    PROJECTS {
        string id PK
    }

    SNAPSHOTS {
        int snapshot_id PK
        string project_id FK
        string label
        datetime created_at
    }

    SNAPSHOT_PROJECTS {
        int snapshot_id PK, FK
        string id PK
        string dsa_component_config_id FK
        string psa_component_config_id FK
        string table_config_id FK
    }

    SNAPSHOT_METAMODELS {
        int snapshot_id PK, FK
        string id PK
        string em_config_id FK
        string fm_config_id FK
        string table_config_id FK
        string optim_config_id FK
    }

    SNAPSHOT_EM_CONFIGS {
        int snapshot_id PK, FK
        string id PK
        string grid_config_id FK
        string generation_config_id FK
        string cs_config_id FK
        string modeldata_config_id FK
        string table_config_id FK
    }

    SNAPSHOT_FM_CONFIGS {
        int snapshot_id PK, FK
        string id PK
        string financedata_config_id FK
        string table_config_id FK
    }

    SNAPSHOT_COMPONENT_CONFIGS {
        int snapshot_id PK, FK
        string id PK
    }

    SNAPSHOT_VARIABLE_CONFIGS {
        int snapshot_id PK, FK
        string id PK
    }

    SNAPSHOT_RESULTS {
        int snapshot_id PK, FK
        int result_id PK
        string component_config_id FK
    }

    SNAPSHOT_PROJECT_METAMODELS {
        int snapshot_id PK, FK
        string project_id PK, FK
        string metamodel_id PK, FK
    }

    SNAPSHOT_PROJECT_VARIABLES {
        int snapshot_id PK, FK
        string project_id PK, FK
        string variable_config_id PK, FK
    }

    SNAPSHOT_METAMODEL_VARIABLES {
        int snapshot_id PK, FK
        string metamodel_id PK, FK
        string variable_config_id PK, FK
    }

    SNAPSHOTS ||--o{ SNAPSHOT_PROJECTS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_METAMODELS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_EM_CONFIGS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_FM_CONFIGS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_COMPONENT_CONFIGS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_VARIABLE_CONFIGS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_RESULTS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_PROJECT_METAMODELS : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_PROJECT_VARIABLES : "contains"
    SNAPSHOTS ||--o{ SNAPSHOT_METAMODEL_VARIABLES : "contains"
    PROJECTS ||--o{ SNAPSHOTS : "snapshotted as"

    SNAPSHOT_PROJECTS ||--o{ SNAPSHOT_PROJECT_METAMODELS : "contains"
    SNAPSHOT_METAMODELS ||--o{ SNAPSHOT_PROJECT_METAMODELS : "belongs to"
    SNAPSHOT_PROJECTS ||--o{ SNAPSHOT_PROJECT_VARIABLES : "has default variables"
    SNAPSHOT_VARIABLE_CONFIGS ||--o{ SNAPSHOT_PROJECT_VARIABLES : "informs"
    SNAPSHOT_METAMODELS ||--o{ SNAPSHOT_METAMODEL_VARIABLES : "has variables"
    SNAPSHOT_VARIABLE_CONFIGS ||--o{ SNAPSHOT_METAMODEL_VARIABLES : "informs"

    SNAPSHOT_METAMODELS }o--|| SNAPSHOT_EM_CONFIGS : "uses"
    SNAPSHOT_METAMODELS }o--|| SNAPSHOT_FM_CONFIGS : "uses"
    SNAPSHOT_COMPONENT_CONFIGS ||--o{ SNAPSHOT_RESULTS : "produces"
    SNAPSHOT_PROJECTS }o--o| SNAPSHOT_COMPONENT_CONFIGS : "DSA, PSA and table configs"
    SNAPSHOT_METAMODELS }o--o| SNAPSHOT_COMPONENT_CONFIGS : "table and optimisation configs"
    SNAPSHOT_EM_CONFIGS }o--o| SNAPSHOT_COMPONENT_CONFIGS : "module configs"
    SNAPSHOT_FM_CONFIGS }o--o| SNAPSHOT_COMPONENT_CONFIGS : "module configs"
```

`snapshots.project_id` refers to the live `projects` table, so a project can be reverted to any
of its snapshots.
