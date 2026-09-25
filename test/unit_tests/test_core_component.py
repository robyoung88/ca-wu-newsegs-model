"""
Unit tests for newsegsmodelframework/core/newsegscomponent.py
"""
from dataclasses import field
from typing import Optional, cast, override
import unittest

from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.trackeddata import revision_dataclass, DataWithRevision
from newsegsmodelframework.core.newsegscomponent import ComponentProperty, NewsegsComponent
from newsegsmodelframework import register_plugins
from newsegsmodelframework.core.constructors import registers

@revision_dataclass
class ChildComponentConfig(DataWithRevision):
    param_a: float = 1
    param_b: float = 1

class ChildComponent(NewsegsComponent):
    @override
    def _generate_config(self, *args, **kwargs) -> DataWithRevision:
        return ChildComponentConfig(*args, **kwargs)

    _config: ChildComponentConfig # pyright: ignore[reportIncompatibleVariableOverride]

@revision_dataclass
class ParentComponentConfig(DataWithRevision):
    n_units: int = 1
    unit_costs: dict = field(default_factory = lambda: dict(fixed = 10., variable = 1.))

class ParentComponent(NewsegsComponent):
    @override
    def _generate_config(self, *args, **kwargs) -> DataWithRevision:
        return ParentComponentConfig(*args, **kwargs)

    child = ComponentProperty(default= lambda: ChildComponent(1,1))

    def __init__(self, *args, child: Optional[ChildComponent], **kwargs):
        super().__init__(*args, **kwargs)
        init_revision = self._config.revision
        if child:
            self.child = child
            self._config._revision = init_revision

ParentComponent._excluded_attributes = tuple(NewsegsComponent._excluded_attributes) + (
    '_child',
)

registers.register_custom_class(ChildComponentConfig._constructor_class, ChildComponentConfig)
registers.register_custom_class(ChildComponent._constructor_class, ChildComponent)
registers.register_custom_class(ParentComponentConfig._constructor_class, ParentComponentConfig)
registers.register_custom_class(ParentComponent._constructor_class, ParentComponent)

class TestComponents(unittest.TestCase):

    def test_parent_and_child(self):
        child_1 = ChildComponent(name = 'Bob', param_a = 1., param_b = 2.)

        self.assertEqual(child_1.name, 'Bob')
        with self.assertRaises(AttributeError):
            nm = child_1._config.name # pyright: ignore[reportAttributeAccessIssue]
        
        self.assertEqual(child_1._config.param_a, 1.)
        self.assertEqual(child_1.param_b, 2.)
        self.assertFalse(child_1.modified)

        parent1 = ParentComponent(n_units = 100, child = child_1)
        self.assertEqual(parent1.n_units, 100)
        self.assertDictEqual(parent1.unit_costs, dict(fixed = 10., variable = 1.))
        self.assertFalse(parent1.modified)

        child_1.param_a = 3.
        self.assertTrue(child_1.modified)
        self.assertTrue(parent1.child.modified)
        self.assertTrue(parent1.chain_modified)
        parent1.chain_syncronise()
        self.assertFalse(parent1.child.modified)
        self.assertFalse(parent1.modified)

    def test_serialisation(self):
        child_1 = ChildComponent(name = 'Bob', param_a = 1., param_b = 2.)
        parent_1 = ParentComponent(n_units = 100, child = child_1)

        child_dict = child_1.to_dict()
        parent_dict = parent_1.to_dict()

        #child_constructor = child_1.from_dict
        #parent_constructor = parent_1.from_dict

        child_constructor = find_constructor(child_dict['constructor_class'], child_dict['class'])
        parent_constructor = find_constructor(parent_dict['constructor_class'], parent_dict['class'])

        child_2 = cast(ChildComponent, child_constructor(child_dict))
        parent_2 = cast(ParentComponent, parent_constructor(parent_dict))

        #with self.assertRaises(AttributeError):
        # Doesn't throw because a default is provided
        #    child = parent_2.child

        self.assertEqual(child_2.id, parent_2._child_id)
        parent_2._child = child_2 # Insert on the private when reconstructing
        self.assertEqual(child_2.modified, parent_2.chain_modified)
        