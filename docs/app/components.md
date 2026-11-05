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
