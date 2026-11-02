"""
Unit tests of the order of the variables of metamodels recovered from the database
"""
import copy
import os
from pathlib import Path
import tempfile
from typing import cast
import unittest

from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db import read_transaction, write_transaction
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework import register_plugins # noqa: F401 - registers the project factories
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsvariable.variable import variable_uid

from config import settings


def _key(varid: str) -> str:
    """The key of a varid, `{section}.{key}`, without its subindex."""
    return varid.rsplit('.', 1)[0]

def _key_order(varids) -> list[str]:
    """The keys of varids in order of first appearance."""
    return list(dict.fromkeys(_key(x) for x in varids))


class TestVariableOrder(unittest.TestCase):
    """Variables of a metamodel are recovered in the order of the metamodel that inserted them"""

    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db

        db_tables.create_all_tables(db.get_engine(writer = True))

    @classmethod
    def tearDownClass(cls):
        from newsegsmodelapp.backend import db

        for writer in (False, True):
            engine = db.get_engine(writer = writer, db_path = cls.db_path)
            engine.dispose()

        cls.db_dir.cleanup()

    def setUp(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        self.proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        self.proj = PROJECT_FACTORIES['sprake']()
        self.mm = self.proj.metamodels[0]
        # Reverse the order of the variables, so that it is not an order the database could find by chance
        variables = list(self.mm.variables.items())
        for varid, _ in variables:
            del self.mm.variables[varid]
        for varid, var in reversed(variables):
            self.mm.variables[varid] = var
        self.original_varids = list(self.mm.variables.keys())

        self.proj_provider.add_component(self.proj)

    def tearDown(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            engine = db.get_engine(writer = writer)
            engine.dispose()

    def test_lightweight_metamodel_order(self):
        lproj = self.proj_provider.get_lightweight_project(self.proj.id)
        self.assertEqual(list(lproj.metamodels[0].variables.keys()), self.original_varids)

    def test_lightweight_metamodel_provider_order(self):
        lmm = self.proj_provider.metamodel_provider.get_lightweight_metamodel(self.mm.id)
        self.assertEqual(list(lmm.variables.keys()), self.original_varids)

    def test_full_metamodel_order(self):
        proj = self.proj_provider.get_project(self.proj.id)
        self.assertEqual(list(proj.metamodels[0].variables.keys()), self.original_varids)

    def test_input_components_in_order(self):
        # The inputs of the DSA and PSA pages are written from top to bottom in the order of the variables
        from newsegsmodelapp.components.composite_input_components import (
            generic_create_dsa_input_container_contents, generic_create_psa_input_container_contents
        )

        def varid_of(component):
            """The varid of the first component id that identifies a variable, searching depth-first."""
            cid = getattr(component, 'id', None)
            if isinstance(cid, dict) and {'section', 'key', 'subindex'} <= cid.keys():
                return f"{cid['section']}.{cid['key']}.{cid['subindex']}"
            children = getattr(component, 'children', None)
            for child in (children if isinstance(children, (list, tuple)) else [children]):
                if child is not None and (varid := varid_of(child)):
                    return varid
            return None

        lmm = self.proj_provider.metamodel_provider.get_lightweight_metamodel(self.mm.id)
        for create in (generic_create_dsa_input_container_contents, generic_create_psa_input_container_contents):
            contents = create(lmm, self.proj_provider.variable_provider)
            self.assertEqual(len(contents), len(self.original_varids))
            # Variables not shown on the page have an empty input, without an id
            shown = [varid for x in contents if (varid := varid_of(x)) is not None]
            self.assertGreater(len(shown), 0)
            self.assertEqual(shown, [x for x in self.original_varids if x in shown])

    def test_order_kept_on_variable_replacement(self):
        # As when the variable of a metamodel is unshared: a new instance replaces the old in the junction table
        lproj = self.proj_provider.get_lightweight_project(self.proj.id)
        lmm = lproj.metamodels[0]
        varid = self.original_varids[len(self.original_varids) // 2]
        var = self.proj_provider.variable_provider.duplicate_variable(lmm.variables[varid])
        lmm.variables[varid] = var.id
        self.proj_provider.add_variables_to_project(lproj.id, [var])
        self.proj_provider.metamodel_provider.refresh_metamodel_variable_junction(
            lmm, [self.proj_provider.variable_provider.get_lightweight_variable(var.id)]
        )

        lmm2 = self.proj_provider.metamodel_provider.get_lightweight_metamodel(self.mm.id)
        self.assertEqual(list(lmm2.variables.keys()), self.original_varids)
        self.assertEqual(lmm2.variables[varid], var.id)

    def test_metamodel_without_key_order(self):
        # Metamodels saved before the order was recorded are still recovered, all their variables included
        import sqlalchemy as sa
        from newsegsmodelapp.backend import db

        with write_transaction(db.get_engine(writer = True)) as conn:
            conn.execute(
                db_tables.metamodel_variables.update()
                .where(db_tables.metamodel_variables.c.metamodel_id == self.mm.id)
                .values(key_order = None)
            )

        lmm = self.proj_provider.metamodel_provider.get_lightweight_metamodel(self.mm.id)
        self.assertEqual(sorted(lmm.variables.keys()), sorted(self.original_varids))
        # The full metamodel falls back to the order of its stored payload
        proj = self.proj_provider.get_project(self.proj.id)
        self.assertEqual(list(proj.metamodels[0].variables.keys()), self.original_varids)

        # Replacing a variable leaves the metamodel without key order, rather than ordering only that variable
        varid = self.original_varids[0]
        var = self.proj_provider.variable_provider.duplicate_variable(lmm.variables[varid])
        lmm.variables[varid] = var.id
        self.proj_provider.add_variables_to_project(self.proj.id, [var])
        self.proj_provider.metamodel_provider.refresh_metamodel_variable_junction(
            lmm, [self.proj_provider.variable_provider.get_lightweight_variable(var.id)]
        )
        with read_transaction(db.get_engine()) as conn:
            key_orders = conn.execute(
                sa.select(db_tables.metamodel_variables.c.key_order)
                .where(db_tables.metamodel_variables.c.metamodel_id == self.mm.id)
            ).scalars().all()
        self.assertTrue(all(x is None for x in key_orders))

    def test_subindex_kept_with_key(self):
        # A subindex of a key that comes after the other keys takes its place with its key
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj = PROJECT_FACTORIES['sprake']()
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        varids = list(mm.variables.keys())
        first_varid = varids[0]
        new_var = copy.deepcopy(mm.variables[first_varid])
        new_var.anonymise_ids()
        new_var.interface_subindex = 1
        new_varid = variable_uid(new_var)
        self.assertEqual(new_varid, f'{_key(first_varid)}.1')
        mm.variables[new_varid] = new_var
        proj.add_variable(new_var)
        self.proj_provider.add_component(proj)

        expected = [first_varid, new_varid] + varids[1:]
        lmm = self.proj_provider.metamodel_provider.get_lightweight_metamodel(mm.id)
        self.assertEqual(list(lmm.variables.keys()), expected)
        self.assertEqual(_key_order(lmm.variables.keys()), _key_order(varids))
        full_proj = self.proj_provider.get_project(proj.id)
        self.assertEqual(list(full_proj.metamodels[0].variables.keys()), expected)


if __name__ == '__main__':
    unittest.main()
