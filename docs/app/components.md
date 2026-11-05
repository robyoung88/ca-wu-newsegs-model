# Components API Reference

Reusable Dash components, layouts and callbacks used by the pages.

| Module | Contents |
|---|---|
| `layouts` | Page building blocks - input cards, results cards and tables, containers |
| `callbacks` | Callbacks for inputs, actions, results and time series |
| `variable_dash_component` | Input components for variables (deterministic, DSA, PSA, optimisation) |
| `navigation` | The navigation bar, including the link to this documentation |
| `colours`, `icons` | The colour scheme of the app and its plots, and the icon library |
| `project_selector`, `configuration_selector`, `map` | Selecting projects, configurations and sites |
| `staleness`, `feedback` | Showing whether results are out of date, indicative energy balances, and the environmental conditions of a site |
| `requesthandler` | Interface for creating and monitoring requests |

## Callbacks with several inputs

Several inputs of a callback can fire in the same call, such as a post-action trigger and the refill interval after a
run, or the active project and the app state on a change of page. Dash lists them all in `ctx.triggered`, but
`ctx.triggered_id` and `callback_utils.get_triggered_value()` give only the first, which may differ in kind (a string
id or a pattern-matching one), in shape, or in what it asks for. A callback with several inputs therefore considers
every trigger, with the helpers of `callback_utils`:

* `get_triggers()` gives each trigger with its id parsed (`Trigger.id` is a string or a dictionary), and none on the
  initial call;
* `get_clicked_trigger()` gives the one button clicked, for a callback with several buttons as inputs: buttons fire
  together, with no clicks, when they are drawn;
* `ids_to_update()` gives the containers to redraw for the triggers: all of them for a string id, otherwise those
  matching a trigger.

Where a callback's decision is more than that, it is a function of its triggers beside the callback (e.g.
`input_headers_to_update`, `timeseries_triggers`), so it can be tested with the triggers which fire together.

## Names

Users name projects, configurations and sites; the app encourages them to:

* **Copies** of a project or configuration are named by
  [`naming.copy_name`][newsegsmodelframework.util.naming.copy_name]: "Baseline (copy)", "Baseline (copy 2)", …, unique
  in the project (or among projects). After a configuration is duplicated, its name box takes the focus with the name
  selected, and is underlined while it has the focus. An uploaded configuration whose name is taken is named as a copy.
* **Unnamed configurations and sites** show a hint in their name box, in sentence case
  (`configuration_selector.CONFIGURATION_NAME_HINT`, `map.SITE_NAME_HINT`), with a short example where the box has room.
  Elsewhere, an unnamed site is shown by its co-ordinates, "Site at 53.255, -3.477".
* **Text users see** says "configuration", never "metamodel", which stays in the code and these docs.

## Styles and colours

Dash serves every stylesheet in `src/assets`, so the app has one: `src/assets/newsegs.css`. It is built, not edited:

* `components/colours.py` holds every colour of the app, in the UI and in plots: the cool off-white background, the
  ClwydAlyn purple of borders and accents (Bootstrap's `primary`), the colours of configurations and the colours of
  other series of plots. The stylesheet takes them as custom properties (`--ns-brand`, `--ns-config-1`, …) and the
  classes `config-colour-1`, `config-colour-2`, ….
* `src/styles` holds the rest of the CSS, as partials, one for each part of the app, in the order of their names. They
  use the custom properties, not colour values.

After changing either, rebuild the stylesheet:

```bash
python scripts/build_css.py
```

A unit test fails while the stylesheet is out of date, or if a partial has a colour value of its own.

A configuration has the same colour everywhere: its icon (`colours.config_colour_class`, `icons.ICON_COLOUR_CLASSES`)
and its series in plots (`colours.config_colour`, `stats.COMPARATOR_COLORS`). Other series take
`colours.SERIES_COLOURS`, which the `newsegs` Plotly template makes the default, or `colours.SEQUENTIAL_COLOURS`.
The configuration colours are chosen to stay distinct for colour-blind users; after changing them, check them with
`python scripts/check_palette.py`.

::: newsegsmodelapp.components
    options:
        show_submodules: true
