# Application plugins

The application has no knowledge of any particular model. Everything specific is added by
**plugins**: Python modules that, on import, add entries to the registries in
[`newsegsmodelapp.registers`][newsegsmodelapp.registers].

`newsegsmodelapp.register_plugins` imports all the plugins, and is imported by `app.py`, the
dispatcher and the workers, so that every process sees the same registries:

1. everything under `newsegsmodelapp.plugins.pages` - **pages must be loaded first**, since
   models configure the pages;
2. everything under `newsegsmodelapp.plugins.models`;
3. the modules in `newsegsmodelapp.components`.

Plugins are found by walking the package, so adding a module in the right place is all that is
needed. The framework's own [project plugins](../framework/plugins.md) are loaded separately by
`app.py` (`import newsegsmodelframework.register_plugins`).

## Directory structure

```text
newsegsmodelapp/plugins/
├── pages/
│   ├── p000_model_selection_layout.py     # /model-selection  (and /)
│   ├── p010_landing_layout.py             # /{model}/landing
│   ├── p100_model_configuration_layout.py # /{model}/site-config
│   ├── p200_dsa_configuration_layout.py   # /{model}/dsa
│   ├── p300_psa_configuration_layout.py   # /{model}/psa
│   └── processes/                         # run requests & procedures launched from pages
│       ├── deterministic_single_mm.py
│       ├── deterministic_run_project.py
│       ├── dsa_single_mm.py
│       ├── dsa_run_project.py             # whole-project DSA (every configuration)
│       ├── psa_single_mm.py
│       ├── psa_run_project.py             # whole-project PSA (every configuration, sharing each draw)
│       ├── optim_single_mm.py
│       └── ...
└── models/
    └── aaa_default/                       # one directory per model type (or group of them)
        ├── page_contents/
        │   ├── configurations.py          # page layout configurations for the model type
        │   ├── inputs/                    # input sections, per page (deterministic, dsa, psa, optim)
        │   └── results/                   # result sections
        ├── processes/
        │   ├── run/
        │   ├── postprocess/               # results -> interface results
        │   │   └── methods/
        │   └── output/                    # table drawing and table getters
        │       └── methods/
        └── utils/                         # e.g. feedback graph artists
```

!!! note "Why `aaa_default`?"
    When a registry is keyed by `model_type`, the first function registered for a key is
    **also registered as the `'default'`** for that key, and is used when no function is
    registered for the model type in use. Plugins are imported in alphabetical order, so the
    directory that provides the defaults is named `aaa_...` to be imported first.
    `aaa_default` currently serves the `sprake` model type.

## Pages

A page is a [`Page`][newsegsmodelapp.types.Page] registered with
[`registers.add_page`][newsegsmodelapp.registers.add_page]. The page `id` is the last element of
the URL (`/{model_type}/{page_id}`), and `app.py` looks the page up and calls its `layout`
function with the [`LayoutConfiguration`][newsegsmodelapp.types.LayoutConfiguration] for the
model type being used.

```python
from dataclasses import dataclass
from dash import html

from newsegsmodelapp import registers
from newsegsmodelapp.components import icons, navigation
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.types import LayoutConfiguration, Page

PAGE_TYPE = 'my-page'

@dataclass
class MyPageLayoutConfiguration(LayoutConfiguration):
    page_type: str = PAGE_TYPE
    title: str = 'My page'               # settings which model types may override

def create_my_page_layout(config: MyPageLayoutConfiguration):
    return html.Div([navigation.create_navigation_component(config.model_type), html.H1(config.title)])

def add_my_page_callbacks(app: NewsegsDash):
    ...                                  # @app.callback(...) definitions

my_page = Page(
    id = PAGE_TYPE,
    nav_label = 'My page',
    nav_icon = html.I(className = icons.get_icon('nav-landing', style_name = 'raw')),
    layout = create_my_page_layout,
    default_configuration = MyPageLayoutConfiguration(),
    attach_callbacks = add_my_page_callbacks,
)
registers.add_page(my_page)
```

* `default_configuration` is registered as the `'default'` configuration for the page. A
  model type customises the page by registering its own configuration with
  [`registers.add_page_layout_configuration`][newsegsmodelapp.registers.add_page_layout_configuration]
  (see `models/aaa_default/page_contents/configurations.py`, which copies the default
  configuration and overrides the text, navigation and input/result sections).
* `attach_callbacks` is called once from `create_app` to bind the page's Dash callbacks.
* Navigation buttons are created from the pages in `PAGE_REGISTER`. A model type chooses which
  appear, and in what order, with the `pages` argument of
  `navigation.create_navigation_component`.
* The `pNNN_` prefix of the page modules is only a convention to set the import order.

## Models

A model type needs its page contents and its processing.

### Page contents

Registered with decorators that take the *supersection* (the page or group of inputs, for
example `dsa`), the optional *section*, and the model type:

```python
@register_input_container_content_creator('dsa', None, 'sprake')
def create_dsa_inputs(...): ...         # builds the Dash components for the inputs

@register_result_container_content_creator(KEY, SECTION, 'sprake')
def create_results(...): ...            # builds the Dash components for a result
```

### Input handlers

`react_to_input_change` (in `components/callbacks/input_container_callbacks.py`) receives almost every change to an
input. An input's id gives its `type`, `purpose`, `supersection`, and the `section`, `key` and `subindex` of its
variable. The callback handles the DSA bounds, bound type and selection, and the optimisation bounds and plot
resolution itself. It passes every other purpose to the handler registered for it:

```python
@register_input_handler('my-purpose', 'input-toggle')        # purpose, component type (None for any)
def handle_my_purpose(triggered_id, input_ids, header_ids, trigger_ids, calling_dict,
                      active_project_id, project_provider, return_dict):
    ...                                  # save the change, mark what it makes stale
    return return_dict                   # with any input_values, header_children and trigger_data set
```

The handler is looked up for the purpose, the component type and the model type in the `app-state` store. It falls
back to the `default` model type, then to any component type. A purpose with no handler makes no update. Each handler
should have a [callback test](../development.md#adding-a-test-of-an-input-handler).

A handler that saves a value shown on the site configuration page, or changes which configurations share a Variable,
should set `return_dict['summary_refresh']`. That redraws the input's sharing summary and its card's label, which
counts the inputs whose configurations differ.

### Lazily built editors

A row can build its editor only when it is opened, so that expensive content isn't built for every row of a page.
`html.Details` doesn't report `open` to callbacks, so the row counts the clicks on its summary instead.
`input_components.create_lazy_input_details` makes the row: a `Details` holding a `Summary`, an empty
`input-group-editor` container, and a hidden `single-input-config` anchor. Dash only calls the callback for a row with a
component matching its first output, and the editor's own inputs don't exist until it's built. When a click opens the row, `react_to_input_change` calls the editor content creator
registered for its supersection and section, and puts what it returns in the container:

```python
@register_input_editor_content_creator('dsa', None, 'sprake')    # supersection, section (None for all), model type
def create_dsa_editor(varid, active_project_id, project_provider) -> list[Component]:
    ...                                  # the children of the editor container
```

Reopening the row builds the editor again, so it shows the current values. Closing it builds nothing.

* Redraw only the children of the editor container, never the `Details` or `Summary`, or the count of clicks and the
  open state will disagree. Rebuilding the whole input container is safe.

The deterministic inputs use this for their group editor (`components/group_editor.py`). Opening an input's sharing
summary shows every group's value, and buttons that move configurations between groups. Selecting a configuration and
choosing where to move it, or dragging its icon to a row, happens in the browser (`assets/group_editor.js`), which
writes the move to the row's `group-move-request` store. A drop moves nothing in the page: the server redraws the
editor, so the script never conflicts with the DOM that React owns. `react_to_input_change` passes moves, and edits of other groups' values (`group-value-input`),
to the handlers in that module. Code that moves configurations between Variables should use `move_metamodels_to_group`,
which keeps the junctions, revisions, staleness and orphaned Variables right.

The DSA rows have a group editor too (`components/dsa_group_editor.py`), in which every group's parameters, bound type
and bounds can be edited. Its focussed row holds the focussed configuration's usual inputs, so the existing handlers
act on them; the other groups' inputs are `group-value-input`s carrying their Variable's id, with the purposes
`group-value`, `group-dsaboundtype`, `group-dsa-bound-lower` and `group-dsa-bound-upper`. A change of a Variable's DSA
settings should go through `set_dsa_bound` or `set_dsa_bound_type`, which save it and mark the DSA stale for the
configurations using it.

The PSA rows follow the same pattern (`components/psa_group_editor.py`): the editor shows the distribution, and each
group's Mean and SD (or Value, for a constant) and confidence interval. The other groups' parameters are edited through
the `group-value` handler. The PSA's selection and its project settings (samples, seed, draws) aren't grouped.
* Don't put interactive components in the `Summary`, since clicks on them are counted too.

### Processes

A *process* is work done in the background by a worker. Processes are chained by naming the
request type that triggers them:

```python
@register_run_request('deterministic_run_metamodel')              # build the request
def request_run(project_id, project_provider, config = None): ...

@register_run_procedure('deterministic_run_metamodel')            # do the work, in a worker
def execute_run(request, project_provider, result_provider, run_id,
                progress_callback, cancelled_callback): ...

@register_postprocess_procedure('postproc_grid', 'sprake',
                                triggers = ['deterministic_run_metamodel'])
def postprocess_grid(...): ...                                    # runs after the trigger

@register_table_draw('results-table', 'sprake', triggers = ['postproc_grid'])
def draw_grid_table(...): ...                                     # runs after postprocessing
```

Processes tied to a page's own functionality (the deterministic, DSA, PSA and optimisation
runs) are in `plugins/pages/processes`, because they are not specific to a model. The
postprocessing and table drawing that translate the results of a model into what is displayed
are in `plugins/models/<model>/processes`.

Every procedure receives the progress and cancellation callbacks from the worker. Return `'ok'` on
success.

### Registers

| Register | Added to with | Keyed by |
|---|---|---|
| `PAGE_REGISTER` | `add_page` | page id |
| `PAGE_LAYOUT_CONFIGURATION_REGISTER` | `add_page_layout_configuration` | page id, model type |
| `INPUT_HANDLERS` | `register_input_handler` | purpose, component type, model type |
| `INPUT_CONTAINER_CONTENT_CREATORS` | `register_input_container_content_creator` | supersection, section, model type |
| `INPUT_EDITOR_CONTENT_CREATORS` | `register_input_editor_content_creator` | supersection, section, model type |
| `INPUT_SECTION_HEADER_CONTENT_CREATORS` | `register_input_section_header_content_creator` | supersection, section, model type |
| `SINGLE_INPUT_HEADER_CONTENT_CREATORS` | `register_single_input_header_content_creator` | supersection, section, model type |
| `RESULT_CONTAINER_CONTENT_CREATORS` | `register_result_container_content_creator` | key, section, model type |
| `RESULT_SECTION_HEADER_CONTENT_CREATORS` | `register_result_section_header_content_creator` | key, section, model type |
| `FEEDBACK_GRAPH_ARTISTS` | `register_feedback_graph_artist` | figure key, model type |
| `RUN_REQUEST_REGISTER` | `register_run_request` | request type |
| `RUN_PROCEDURE_REGISTER` | `register_run_procedure` | request type |
| `POSTPROCESS_REQUEST_REGISTER` | `register_postprocess_request` | postprocess type |
| `POSTPROCESS_REGISTER` | `register_postprocess_procedure` | process, model type |
| `TABLE_DRAW_REQUEST_REGISTER` | `register_table_draw_request` | table draw type |
| `TABLE_DRAW_REGISTER` | `register_table_draw` | table section, model type |
| `TABLE_GETTER_REGISTER` | `register_table_getter` | table section, model type |
| `TABLE_SUBINDEX_MAPS` | `register_table_subindex_map` | table section, model type |
| `POST_ACTION_REGISTER` | `triggers` argument of the procedure decorators | triggering request type |

## Adding a model type

1. Add a [project plugin](../framework/plugins.md) to the framework, registering the model type.
2. Add the model type to `AVAILABLE_MODELS` in `src/app.py`, and a button for it on the model
   selection page (`p000_model_selection_layout.py`).
3. Add a directory in `newsegsmodelapp/plugins/models/` with the page configurations, input and
   result sections, and processing for the model type. Anything not provided falls back to the
   `default` registrations.

## API

::: newsegsmodelapp.registers
    options:
        members_order: source

::: newsegsmodelapp.types

::: newsegsmodelapp.dash_extension

## Plugin modules

::: newsegsmodelapp.plugins
    options:
        show_submodules: true
