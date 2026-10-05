"""
Unit tests for newsegsmodelframework/core/newsegscomponent.py
"""
import copy
from dataclasses import field
from typing import Optional, cast, override
import unittest

from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.trackeddata import ComponentProperty, revision_dataclass, DataWithRevision
from newsegsmodelframework.core.newsegscomponent import DictionaryComponentProvider, NewsegsComponent
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

    # @override
    # def get_component_attributes(self) -> tuple[str, ...]:
    #     return ('child', *super().get_component_attributes())
    

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

        provider = DictionaryComponentProvider(
            {
                child_1.id: child_1,
                parent_1.id: parent_1
            }
        )

        child_dict = child_1.to_dict()
        parent_dict = parent_1.to_dict()

        #child_constructor = child_1.from_dict
        #parent_constructor = parent_1.from_dict

        child_constructor = find_constructor(child_dict['constructor_class'], child_dict['class'])
        parent_constructor = find_constructor(parent_dict['constructor_class'], parent_dict['class'])

        child_2 = cast(ChildComponent, child_constructor(child_dict))
        parent_2 = cast(ParentComponent, parent_constructor(parent_dict))

        self.assertEqual(child_2.id, parent_2._component_ids['child'])

        parent_2.reattach_components(provider)
        self.assertIs(parent_2.child, parent_1.child)
        self.assertEqual(child_2.modified, parent_2.chain_modified)

    def test_copy(self):
        child_1 = ChildComponent(name = 'Bob', param_a = 1., param_b = 2.)
        parent_1 = ParentComponent(n_units = 100, child = child_1)

        parent_2 = copy.deepcopy(parent_1)
        self.assertFalse(parent_2.child is parent_1.child)
        self.assertEqual(parent_2.child.name, parent_1.child.name)
        