"""
The test case of the callback tests: a temporary database, a project, and a minimal app holding the input container
callbacks.

Each test has its own database and app, so nothing carries over between tests: the engines are disposed of, and the
providers (with any caches) and the app are created again. Subclasses choose the provider of the app with
`provider_class`; the database is read back with a separate, uncached provider, so assertions see what is stored.
"""
import os
from pathlib import Path
import tempfile
import time
from typing import Any, cast
import unittest

from dash import html
import sqlalchemy as sa

from config import settings

# Fill the registers, as the app does on import. Python imports a module once per process, so the registration (which
# raises on duplicates) happens once, whichever test runs first.
import newsegsmodelframework.register_plugins  # noqa: F401
import newsegsmodelapp.register_plugins  # noqa: F401

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_component_provider import (
    CachedFromDatabaseNewsegsProjectProvider,
    FromDatabaseNewsegsProjectProvider,
)
from newsegsmodelapp.components.callbacks.input_container_callbacks import add_input_container_callbacks
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

from .dash_dispatch import CallbackResponse, dispatch_input_change, render_input_containers

MODEL_TYPE = 'sprake'

class _Unused:
    """Stands in for the providers that the input container callbacks do not use"""
    def __getattr__(self, name):
        raise AttributeError(f'{name} is not available to the callback tests')

class InputChangeTestCase(unittest.TestCase):
    """Base of the tests of `react_to_input_change`.

    Attributes:
        provider_class: Class of the project provider of the app.
        n_metamodels: Number of configurations of the project, all sharing their variables.
    """
    provider_class: type[FromDatabaseNewsegsProjectProvider] = FromDatabaseNewsegsProjectProvider
    n_metamodels: int = 1

    def setUp(self):
        self._db_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.db_path = Path(self._db_dir.name) / 'tempdb.db'

        self._old_db_path = os.environ.get('DYNACONF_DB_PATH')
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        self.engine = db.get_engine(writer = True)
        tbls.create_all_tables(self.engine)

        # Reads back what is stored, bypassing any cache of the app's provider
        self.reader = FromDatabaseNewsegsProjectProvider(db.get_engine)

        project = PROJECT_FACTORIES[MODEL_TYPE]()
        self.reader.add_component(project)
        self.project_id = project.id
        for _ in range(self.n_metamodels - 1):
            self.add_configuration()
        self.set_focus(0)

        self.provider = self.provider_class(db.get_engine)
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = cast(Any, _Unused()),
            request_handler = cast(Any, _Unused()),
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        add_input_container_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

    def tearDown(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()

        if self._old_db_path is None:
            del os.environ['DYNACONF_DB_PATH']
        else:
            os.environ['DYNACONF_DB_PATH'] = self._old_db_path
        settings.reload()

        self._db_dir.cleanup()

    # -----------------------------------------------------------------------
    # Setting up the project, as the app does
    # -----------------------------------------------------------------------

    def add_configuration(self, from_index: int = 0) -> str:
        """Duplicate a configuration, as the configuration selector does; the copy shares every variable.

        Returns:
            Id of the new configuration.
        """
        proj = self.reader.get_project(self.project_id)
        new_mm = cast(NewsegsMetaModel, self.reader.metamodel_provider.duplicate_component(proj.metamodels[from_index].id))
        new_mm.reattach_variables(proj)
        proj.metamodels.append(new_mm) # pyright: ignore[reportAttributeAccessIssue]
        self.reader.upsert_component(proj)
        return new_mm.id

    def set_focus(self, mm_index: int):
        """Focus a configuration, as the configuration selector does."""
        lproj = self.reader.get_lightweight_project(self.project_id)
        self.reader.set_component_metadata(
            self.project_id, 'focussed_metamodel_id', lproj.metamodels[mm_index].id, increment_revision = False
        )

    def make_independent(self, mm_index: int, varid: str) -> str:
        """Give a configuration its own instance of a variable, copied from the one it shares.

        Returns:
            Id of the new variable instance.
        """
        lproj = self.reader.get_lightweight_project(self.project_id)
        lmm = lproj.metamodels[mm_index]
        var = self.reader.variable_provider.duplicate_variable(lmm.variables[varid])
        lmm.variables[varid] = var.id
        self.reader.add_variables_to_project(self.project_id, [var])
        self.reader.metamodel_provider.refresh_metamodel_variable_junction(
            lmm, [self.reader.variable_provider.get_lightweight_variable(var.id)]
        )
        # As moving a configuration between groups does, which tells caches of the project that it has changed
        self.reader.metamodel_provider.increment_revision(lmm.id)
        self.reader.increment_revision(self.project_id)
        return var.id

    def remove_configuration(self, mm_index: int):
        """Remove a configuration, as the configuration selector does."""
        proj = self.reader.get_project(self.project_id)
        mm = proj.metamodels.pop(mm_index) # pyright: ignore[reportAttributeAccessIssue]
        self.reader.metamodel_provider.delete_component(mm.id)
        proj.set_focussed_metamodel_index(proj.get_focussed_metamodel_index())
        self.reader.upsert_component(proj)

    # -----------------------------------------------------------------------
    # Dispatch
    # -----------------------------------------------------------------------

    def page(self, *containers: tuple[str, str | None]) -> list:
        """The components of input containers, rendered by the app for the active project."""
        return render_input_containers(self.provider, self.project_id, containers, MODEL_TYPE)

    def dispatch(self, trigger: dict, value: Any, components: list, **kwargs) -> CallbackResponse:
        """Dispatch a change of an input of the active project to `react_to_input_change`."""
        kwargs.setdefault('project_id', self.project_id)
        kwargs.setdefault('model_type', MODEL_TYPE)
        return dispatch_input_change(self.client, trigger, value, components = components, **kwargs)

    # -----------------------------------------------------------------------
    # What is stored
    # -----------------------------------------------------------------------

    @property
    def metamodel_ids(self) -> list[str]:
        """Ids of the configurations, in order."""
        return [x.id for x in self.reader.get_lightweight_project(self.project_id).metamodels]

    def variable_uid(self, varid: str, mm_index: int = 0) -> str:
        """Id of the instance of a variable that a configuration holds, as stored."""
        return self.reader.get_lightweight_project(self.project_id).metamodels[mm_index].variables[varid]

    def stored_variable(self, varid: str, mm_index: int = 0):
        """The variable that a configuration holds, as stored."""
        return self.reader.variable_provider.get_variable(self.variable_uid(varid, mm_index))

    def loaded_variable(self, varid: str, mm_index: int = 0):
        """The variable that a configuration loads with its project, as stored."""
        return self.reader.get_project(self.project_id).metamodels[mm_index].variables[varid]

    def _rows(self, table: sa.Table, *columns: str) -> dict:
        pk = [x.name for x in table.primary_key.columns]
        with read_transaction(self.engine) as conn:
            rows = conn.execute(sa.select(table)).mappings().fetchall()
        return {
            tuple(x[k] for k in pk): tuple(x[c] for c in columns) if columns else dict(x)
            for x in rows
        }

    def revisions(self) -> dict[str, dict]:
        """Revision of every project, configuration, component and variable, by table."""
        return {
            table.name: self._rows(table, 'revision')
            for table in (tbls.projects, tbls.metamodels, tbls.component_configs, tbls.variable_configs)
        }

    def revised(self, before: dict[str, dict]) -> dict[str, set]:
        """The primary keys of the rows of each table whose revision has changed since `before`."""
        after = self.revisions()
        return {
            name: {k for k, v in rows.items() if before[name].get(k) != v}
            for name, rows in after.items()
        }

    def stale_marks(self, since_ns: int) -> set[tuple[str, str]]:
        """(configuration id, process) pairs whose inputs have been marked changed since a time."""
        rows = self._rows(tbls.process_staleness, 'inputs_changed_ns')
        return {k for k, (changed_ns,) in rows.items() if changed_ns is not None and changed_ns >= since_ns}

    def database_state(self) -> dict[str, Any]:
        """Every row of the tables that input changes can affect, for checking that nothing changed."""
        return {
            table.name: self._rows(table)
            for table in (
                tbls.projects, tbls.metamodels, tbls.component_configs, tbls.variable_configs,
                tbls.project_variables, tbls.metamodel_variables, tbls.process_staleness,
            )
        }

    def now(self) -> int:
        """The time, in the units of the staleness records."""
        return time.time_ns()

    def assertNothingChanged(self, before: dict[str, Any]):
        """Assert that the database is as `database_state` found it."""
        after = self.database_state()
        for name, rows in before.items():
            self.assertEqual(after[name], rows, f'Rows of {name} have changed')

def cached_variant(cls: type[InputChangeTestCase]) -> type[InputChangeTestCase]:
    """A subclass of a test case whose app uses `CachedFromDatabaseNewsegsProjectProvider`, as the app does.

    Assign it to a module-level name beginning `Test`, so that it is collected.
    """
    return type(
        f'{cls.__name__}Cached', (cls,),
        {
            'provider_class': CachedFromDatabaseNewsegsProjectProvider,
            '__doc__': f'{cls.__doc__} (with the cached project provider)',
            '__module__': cls.__module__,
        },
    )
