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

        # Mutate a primitive with equal value
        parent.val = 20
        self.assertEqual(parent.revision, 0)

        # Mutate a primitive with new value
        parent.val = 21
        self.assertEqual(parent.revision, 1)

        # Mutate a list member
        child.tags[0] = 'ham'
        self.assertListEqual(child.tags, ['ham', 'eggs'])
        self.assertEqual(child.revision, 1)
        self.assertEqual(parent.revision, 2)

        subchild = Node(
            val = 1,
            tags = ['sub'],
            meta = {},
            immut = (7, 8, 9)
        )
        # Mutate a dict
        child.meta['c'] = subchild
        self.assertEqual(child.revision, 2)
        self.assertEqual(parent.revision, 3)

        subchild.immut = (10,)
        self.assertEqual(subchild.revision, 1)
        self.assertEqual(child.revision, 3)
        self.assertEqual(parent.revision, 4)

    #def test_chained_increments(self):