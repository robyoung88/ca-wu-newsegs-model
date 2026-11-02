"""The database layer: tables, providers of components, variables and results, requests, snapshots and staleness.

The names used outside the package are exposed here; the rest is in the modules.

Modules:
    db: Creation and management of the database, and read and write transactions.
    db_tables: The table definitions (described in the database page of the documentation).
    db_component_provider: Providers of components - NewSEGS Energy Models, finance models, metamodels and projects.
    db_variable_provider: Providers of variables.
    db_result_provider: Providers of results.
    db_request_handler: Creation and monitoring of requests for background procedures.
    db_jobs: Updates to the runs of requests.
    db_snapshot: Snapshots of projects.
    db_staleness: Whether the results of a process are out of date.
    project: Functions for projects.
"""
from .db import get_engine, init_db, DependentObjectsExistError
import newsegsmodelapp.backend.db.db_tables as tables
from . import db_snapshot # Imported so that it is available as an attribute of the package

__all__ = [
    'get_engine',
    'init_db',
    'DependentObjectsExistError',
    'tables',
]
