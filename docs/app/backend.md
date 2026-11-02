# Backend API Reference

The backend contains everything that does not draw the user interface. Its processes are
started separately from the Dash app (`docker-compose.yml`):

| Module | Purpose | Service |
|---|---|---|
| `newsegsmodelapp.backend.dispatcher` | Proxy between the front end and the workers; supervises workers and writes a heartbeat file | `zmq-dispatcher` |
| `newsegsmodelapp.backend.worker` | Executes requests - looks up and calls the registered procedures | started by the dispatcher |
| `newsegsmodelapp.backend.maintenance` | Schedules backups and pruning | `maintenance-cron` |
| `newsegsmodelapp.backend.db` | Database access, providers and tables | all |

The database layer includes *providers* - implementations of the framework's provider
interfaces (`NewsegsProjectProviderInterface`, `NewsegsResultProviderInterface`) which read and
write projects, components, variables and results to the [database](database.md) and results
store, with caching - and the request handler.

::: newsegsmodelapp.backend.db
    options:
        show_submodules: true

::: newsegsmodelapp.backend.dispatcher

::: newsegsmodelapp.backend.worker

::: newsegsmodelapp.backend.maintenance

::: newsegsmodelapp.backend.backup

::: newsegsmodelapp.backend.pruning
