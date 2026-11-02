"""Backend of the app: everything that does not draw the user interface.

Modules:
    db: The database layer - tables, providers and requests.
    dispatcher: Proxy between the front end and the workers.
    worker: Executes requests in the background.
    maintenance: Scheduled backups and pruning.
    backup: The backup of the database.
    pruning: Removal of old runs, results and files.
    constants: Constants of the backend.
"""
