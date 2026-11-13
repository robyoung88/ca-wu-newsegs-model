# Application overview

`newsegsmodelapp` is the web application for the NewSEGS model. It is a multi-page
[Dash](https://dash.plotly.com) app (entry point `src/app.py`) supported by a SQLite database
and background workers.

```text
src/
├── app.py                   # creates the Dash app (NewsegsDash) and binds callbacks
├── app_logging.py
├── settings.toml            # settings read by config.settings
└── newsegsmodelapp/
    ├── registers.py         # registries that plugins add to (see Plugins)
    ├── register_plugins.py  # imports every plugin
    ├── types.py             # Page and LayoutConfiguration
    ├── dash_extension.py    # NewsegsDash - Dash app which holds the providers
    ├── backend/             # database, dispatcher, workers, maintenance
    ├── components/          # reusable Dash components, layouts and callbacks
    └── plugins/
        ├── pages/           # the pages of the app and the processes they launch
        └── models/          # model-type specific inputs, results and processing
```

| Section | Contents |
|---|---|
| [Plugins](plugins.md) | How to add pages and model types to the app |
| [Backend](backend.md) | Database layer, dispatcher, workers and maintenance |
| [Components](components.md) | Reusable components, layouts and callbacks |
| [Database](database.md) | Tables and relationships |

## Running a model

1. A user acts on a page (for example presses *run*). A callback calls the *run request*
   function registered for that action, which creates a `RunRequest` that is written to the
   `requests` table.
2. The front end's **action manager** (`manage_actions`, in `components/callbacks/action_callbacks.py`) picks up
   `AWAITING DISPATCH` requests and sends them over ZeroMQ to the **dispatcher**, which hands each to a **worker**.
3. The worker creates a `run`, looks up the *run procedure* registered for the request type and
   executes it, updating the run's progress and checking whether cancellation has been requested.
   Results are written to the results store and recorded in `results`.
4. Completing a request triggers its **post-actions**: *postprocess* procedures convert
   results into the form needed by the interface, and *table draw* procedures prepare the
   tables. These are themselves requests, executed in the same way.
5. The front end polls the `runs` table for progress and, when the run completes, loads the
   results and updates the page.

## Documentation inside the app

The HTML of these pages is built with `mkdocs build` into the `site/` directory, from where
the app serves it at `/documentation/`. The help button on the navigation bar, and the
documentation link on the model selection page, open it; the *Back to the app* link in the
documentation header returns to the app launch page. The `DOCS_PATH` setting (see
`src/settings.toml`) overrides the directory that is served. The Docker image builds the
documentation as part of the image build.
