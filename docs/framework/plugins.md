# Framework plugins

The framework is extended by two mechanisms, both of which take effect simply by importing the
module that does the registration:

1. **Project factories** - make a new *model type* available to applications.
2. **Constructor registries** - make new component classes (modules, finance, variables...)
   reconstructable when a stored configuration is loaded.

## Directory structure

```text
newsegsmodelframework/
├── register_plugins.py          # imports every module in plugins/projects
└── plugins/
    ├── registers.py             # PROJECT_FACTORIES and @register_project_factory
    └── projects/
        ├── __init__.py
        └── sprake.py            # the plugin for the "sprake" model type
```

`newsegsmodelframework.register_plugins` is imported by the application at start-up
(`import newsegsmodelframework.register_plugins` in `app.py`). On import it walks
`newsegsmodelframework.plugins.projects` and imports each module in it, so a plugin consists
of **dropping a module into `plugins/projects/`**; no list needs to be edited.

## Writing a project plugin

A project plugin is a module containing a function, decorated with
[`register_project_factory`][newsegsmodelframework.plugins.registers.register_project_factory],
which returns a fully configured `NewsegsProject`. The name passed to the decorator is the
*model type* - it is the first element of the URL of the app (`/{model_type}/{page}`), is stored
with each project in the database, and is used by the
[application plugins](../app/plugins.md) to find the pages and processing for the model.

The first factory registered is also registered under `'default'`, which is the fallback for
unknown model types.

```python
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.plugins.registers import register_project_factory

MODEL_TYPE = 'mymodel'

@register_project_factory(MODEL_TYPE)
def my_project_factory() -> NewsegsProject:
    model = ...      # a NewsegsModel subclass, with its modules configured
    finance = ...    # a NewsegsFinance subclass; call finance.set_model(model)
    variables = ...  # list[Variable] characterising the parameters

    project = NewsegsProject(
        default_variables = variables,
        model_type = MODEL_TYPE,
        model_version = model.version,
    )
    varids = project.get_varids()
    metamodel = NewsegsMetaModel(
        model, finance,
        variables = [project.get_default_variable(x) for x in varids]
    )
    project.metamodels.append(metamodel)
    return project
```

`plugins/projects/sprake.py` is the worked example: it loads the validated Sprake model and
finance configurations and default variables from the `data/` directory.

!!! note
    While the factory builds the project, revision notifications are disabled with
    `RevisionNotifierMixin._set_notification_state('disabled')` and revisions are reset
    afterwards (`reset_revision(chain = True)`), so that the new project does not start life
    looking modified.

## Adding component classes

Stored configurations are dictionaries that name the class that they describe. When the app loads
them it calls [`find_constructor`][newsegsmodelframework.core.find_constructor] with a
*constructor class* and a class name, to get a callable that builds the object from the
dictionary.

The registry of classes for each constructor class is built by functions decorated with
[`register_constructor_class`][newsegsmodelframework.core.constructors.registers.register_constructor_class] in
`newsegsmodelframework/core/constructors/registers.py`. The built-in registries
find classes by inspecting the `__all__` of the framework packages, so:

* a new subclass of an existing kind (for example another `NewsegsGeneration`) is discovered
  automatically **if it is exported in the `__all__` of its package** (`newsegsgeneration`,
  `newsegsgrid`, `newsegscs`, `newsegsmodel`, `newsegsfinance`...);
* a class that lives outside these packages, for instance in a separate plugin package, can be
  added at runtime with
  [`register_custom_class(constructor_class, cls)`][newsegsmodelframework.core.constructors.registers.register_custom_class];
* an entirely new family of classes needs its own `@register_constructor_class('Name')`
  function, and the family's base class should set `_constructor_class = 'Name'`.

The constructor classes are `DataWithRevision`, `NewsegsComponent`, `NewsegsModule`, `Generator`,
`Environment`, `Location`, `TimeSpan`, `Timestamp`, `Timedelta`, `datetime`, `PVLib` and
`Variable`.

## API

::: newsegsmodelframework.plugins.registers

The registries and `register_constructor_class` are documented with the [core components](core.md).
