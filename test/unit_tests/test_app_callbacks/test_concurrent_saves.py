"""
A test that a change saved in one request is kept while other requests load components, as they do in the threads of
the Dash server: duplicating a configuration, as the configuration selector does.
"""
import threading
from typing import cast

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

TestSaveDuringLoadsCached = cached_variant(TestSaveDuringLoads)
