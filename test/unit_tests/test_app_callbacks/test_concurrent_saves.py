"""
A test that a change saved in one request is kept while other requests load components, as they do in the threads of
the Dash server: duplicating a configuration, as the configuration selector does.
"""
import random
import threading
from typing import cast

import sqlalchemy as sa

from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

from .base import InputChangeTestCase, cached_variant

class TestSaveDuringLoads(InputChangeTestCase):
    """Duplicating a configuration while other threads load components"""

    def setUp(self):
        super().setUp()
        # As after any input change: the project's row has a later revision than its payload
        self.reader.increment_revision(self.project_id)

    def test_duplicate_kept(self):
        mm_ids = self.metamodel_ids
        stop = threading.Event()
        def load_repeatedly():
            while not stop.is_set():
                self.provider.metamodel_provider.get_lightweight_component(mm_ids)
        loaders = [threading.Thread(target = load_repeatedly) for _ in range(3)]
        for x in loaders:
            x.start()
        try:
            # add_duplicate_config
            proj = self.provider.get_project(self.project_id)
            new_mm = cast(NewsegsMetaModel, self.provider.metamodel_provider.duplicate_component(proj.metamodels[0].id))
            new_mm.reattach_variables(proj)
            proj.metamodels.append(new_mm) # pyright: ignore[reportAttributeAccessIssue]
            proj.set_focussed_metamodel(new_mm.id)
            self.provider.upsert_component(proj)
        finally:
            stop.set()
            for x in loaders:
                x.join(timeout = 10)

        for provider in (self.reader, self.provider):
            lproj = provider.get_lightweight_project(self.project_id)
            self.assertEqual([x.id for x in lproj.metamodels], mm_ids + [new_mm.id])
            self.assertEqual(lproj.focussed_metamodel_index, 1)

class TestFocusSeenThroughAnyConnection(InputChangeTestCase):
    """A change of focus is seen by every read, whichever pooled connection it uses.

    The readers' connections are used unevenly by the threads of the server, so their counts of SQLite's
    `data_version` drift apart. A cache comparing those counts across connections returned stale projects.
    """
    n_metamodels = 3

    def drift_connections(self, rng: random.Random):
        """Use some pooled connections and not others between writes, as the threads of the server do"""
        from newsegsmodelapp.backend import db
        connections = [db.get_engine().connect() for _ in range(rng.randint(1, 5))]
        for _ in range(rng.randint(0, 3)):
            self.reader.set_component_metadata(self.project_id, 'label', f'{rng.random()}', increment_revision = False)
            for conn in rng.sample(connections, rng.randint(0, len(connections))):
                conn.execute(sa.text('select 1')).fetchall()
        for conn in connections:
            conn.close()

    def test_focus_change_seen(self):
        # Seeded, so that the pool is used in the same way each time; this sequence returned a stale focus before
        rng = random.Random(1)
        mm_ids = self.metamodel_ids
        self.provider.get_lightweight_project(self.project_id)
        stale = []
        for i in range(400):
            self.drift_connections(rng)
            target = i % 3
            # set_focussed_config
            self.provider.set_component_metadata(
                self.project_id, 'focussed_metamodel_id', mm_ids[target], increment_revision = False
            )
            focus = self.provider.get_lightweight_project(self.project_id).focussed_metamodel_index
            if focus != target:
                stale.append((i, target, focus))
        self.assertEqual(stale, [])

TestSaveDuringLoadsCached = cached_variant(TestSaveDuringLoads)
TestFocusSeenThroughAnyConnectionCached = cached_variant(TestFocusSeenThroughAnyConnection)
