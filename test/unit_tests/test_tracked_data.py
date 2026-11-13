"""
Unit tests for newsegsmodelframework/core/trackeddata.
"""
from dataclasses import dataclass, asdict
import threading
from typing import Optional
import unittest

from newsegsmodelframework.core.trackeddata import revision_dataclass, DataWithRevision, RevisionNotifierMixin

@revision_dataclass
class Node(DataWithRevision):
    val: int
    tags: list
    meta: dict
    immut: tuple['int | Node' , ...]
    child: Optional['Node'] = None

def create_parent_and_child() -> tuple[Node, Node]:
    child = Node(
        val = 2, 
        tags = ['spam', 'eggs'], 
        meta = {'a': 4, 'b': 8},
        immut = (1, 2, 3)
    )

    parent = Node(
        val = 20,
        tags = ['ni', 'ni'],
        meta = {'a': 40, 'b': 80},
        immut = (4, 5, 6),
        child = child
    )

    return parent, child

class TestRevisionIncrements(unittest.TestCase):

    def test_parent_and_child(self):
        parent, child = create_parent_and_child()

        self.assertEqual(child.revision, 0)
        
        self.assertEqual(parent.revision, 0)
        

        self.assertFalse(parent.modified)

        # Mutate a primitive with equal value
        parent.val = 20
        self.assertEqual(parent.revision, 0)
        self.assertFalse(parent.modified)
        
        # Mutate a primitive with new value
        parent.val = 21
        self.assertEqual(parent.revision, 1)
        self.assertTrue(parent.modified)
        parent._syncronise()
        self.assertFalse(parent.modified)

        # Mutate a list member
        child.tags[0] = 'ham'
        self.assertListEqual(child.tags, ['ham', 'eggs'])
        self.assertEqual(child.tags.revision, 1) # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(parent.revision, 2)
        self.assertTrue(child.tags.modified) # pyright: ignore[reportAttributeAccessIssue]
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
        parent._chain_syncronise()
        self.assertFalse(parent.chain_modified)

        subchild = Node(
            val = 1,
            tags = ['sub'],
            meta = {},
            immut = (7, 8, 9)
        )
        # Mutate a dict
        child.meta['c'] = subchild
        self.assertTrue(parent.chain_modified)
        self.assertFalse(subchild.modified)
        parent._chain_syncronise()

        subchild.immut = (10,)
        self.assertTrue(parent.chain_modified)

        # Remove subchild
        child.meta.pop('c')
        self.assertTrue(parent.chain_modified)
        parent._chain_syncronise()
        self.assertFalse(parent.chain_modified)
        self.assertTrue(subchild.chain_modified)

        # subchild as immutable
        child.immut = (subchild,)
        self.assertTrue(parent.chain_modified)
        parent._chain_syncronise()
        self.assertFalse(parent.chain_modified)
        self.assertFalse(subchild.chain_modified)

    def test_serialisation(self):
        parent, child = create_parent_and_child()
        d1 = parent.to_dict()


    #def test_chained_increments(self):
class TestNotificationStateThreads(unittest.TestCase):
    """The notification state is held for each thread: loading components disables it only in the loading thread.

    A process-wide state let a load in one thread (e.g. one request of the Dash server) hide the changes made in
    another, and overlapping loads could restore it in the wrong order, leaving it disabled for the whole process.
    """

    def setUp(self):
        self.node, _ = create_parent_and_child()
        self.node._syncronise()

    def run_in_thread(self, target):
        errors = []
        def wrapped():
            try:
                target()
            except BaseException as e:  # Reraised in the test's thread
                errors.append(e)
        thread = threading.Thread(target = wrapped)
        thread.start()
        return thread, errors

    def join(self, thread, errors):
        thread.join(timeout = 10)
        self.assertFalse(thread.is_alive())
        if errors:
            raise errors[0]

    def test_disabled_in_this_thread(self):
        prevstate = RevisionNotifierMixin._set_notification_state('disabled')
        try:
            self.node.val += 1
            self.assertEqual(self.node.revision, 0)
        finally:
            RevisionNotifierMixin._set_notification_state(prevstate)
        self.node.val += 1
        self.assertEqual(self.node.revision, 1)

    def test_disabled_in_another_thread_does_not_hide_changes(self):
        disabled, done = threading.Event(), threading.Event()
        def load():
            prevstate = RevisionNotifierMixin._set_notification_state('disabled')
            disabled.set()
            done.wait(timeout = 10)
            RevisionNotifierMixin._set_notification_state(prevstate)

        thread, errors = self.run_in_thread(load)
        try:
            self.assertTrue(disabled.wait(timeout = 10))
            self.node.val += 1
            self.assertEqual(self.node.revision, 1)
        finally:
            done.set()
            self.join(thread, errors)

    def test_overlapping_loads_leave_notification_enabled(self):
        # A disables, B disables, A restores, B restores: B must not restore A's disabled state
        a_set, b_set, a_restored = threading.Event(), threading.Event(), threading.Event()
        previous = {}
        def load_a():
            previous['a'] = RevisionNotifierMixin._set_notification_state('disabled')
            a_set.set()
            b_set.wait(timeout = 10)
            RevisionNotifierMixin._set_notification_state(previous['a'])
            a_restored.set()
        def load_b():
            a_set.wait(timeout = 10)
            previous['b'] = RevisionNotifierMixin._set_notification_state('disabled')
            b_set.set()
            a_restored.wait(timeout = 10)
            RevisionNotifierMixin._set_notification_state(previous['b'])

        threads = [self.run_in_thread(load_a), self.run_in_thread(load_b)]
        for thread, errors in threads:
            self.join(thread, errors)

        self.assertEqual(previous, {'a': 'broadcast', 'b': 'broadcast'})
        self.assertEqual(RevisionNotifierMixin._get_notification_state(), 'broadcast')
        self.node.val += 1
        self.assertEqual(self.node.revision, 1)
