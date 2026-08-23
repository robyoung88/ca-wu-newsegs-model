"""
Unit tests for newsegsmodelframework/core/trackeddata.
"""
from dataclasses import dataclass
from typing import Optional
import unittest

from newsegsmodelframework.core.trackeddata import revision_dataclass, DataWithRevision

@revision_dataclass
class Node(DataWithRevision):
    val: int
    tags: list
    meta: dict
    immut: tuple[int, ...]
    child: Optional['Node'] = None

class TestRevisionIncrements(unittest.TestCase):

    def test_parent_and_child(self):
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
        self.assertEqual(parent.revision, 1)
        self.assertTrue(child.tags.modified) # pyright: ignore[reportAttributeAccessIssue]
        self.assertFalse(parent.modified)
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

    #def test_chained_increments(self):