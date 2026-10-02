from dataclasses import field
from typing import Any, Iterable, Optional, override
import unittest

from useful_types import SequenceNotStr

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.trackeddata import ComponentListProperty, ComponentOrderedDictProperty, DataWithRevision, revision_dataclass

@revision_dataclass
class ChildConfig(DataWithRevision):
    simple_prop: int = 0
    list_prop: list[Any] = field(default_factory=list)
    obj_prop: dict[str, Any] = field(default_factory=dict)


@revision_dataclass
class DummyConfig(DataWithRevision):
    ...

class ChildComponent(NewsegsComponent):
    
    @override
    def _generate_config(self, *args, **kwargs) -> ChildConfig:
        return ChildConfig(*args, **kwargs)
    _config: ChildConfig # pyright: ignore[reportIncompatibleVariableOverride]

class ParentOfList(NewsegsComponent):

    @override
    def _generate_config(self, *args, **kwargs) -> DummyConfig:
        return DummyConfig(*args, **kwargs)
    _config: DummyConfig # pyright: ignore[reportIncompatibleVariableOverride]

    components_children = ComponentListProperty(oftype = ChildComponent)

    def __init__(
        self,
        *args,
        children: Optional[SequenceNotStr[ChildComponent]] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        if children is None:
            children = []
        self.components_children = [x for x in children]
        self.revision = 0

ParentOfList._excluded_attributes = super(ParentOfList, ParentOfList)._excluded_attributes + (
    '_components_children',
)

class ParentOfOrderedDict(NewsegsComponent):
    @override
    def _generate_config(self, *args, **kwargs) -> DummyConfig:
        return DummyConfig(*args, **kwargs)
    _config: DummyConfig # pyright: ignore[reportIncompatibleVariableOverride]

    variables = ComponentOrderedDictProperty(oftype = ChildComponent)

    def __init__(
        self,
        *args,
        children: Optional[SequenceNotStr[ChildComponent]] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        if children is None:
            children = []
        self.variables = {x.name: x for x in children}
        self.revision = 0

ParentOfOrderedDict._excluded_attributes = super(ParentOfOrderedDict, ParentOfOrderedDict)._excluded_attributes + (
    '_variables',
)


class TestChildComponentProperties(unittest.TestCase):

    def test_list_creation_and_modification(self):
        child1 = ChildComponent(name = 'child1')
        child2 = ChildComponent(name = 'child2')

        parent = ParentOfList(children = [child1, child2])

        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)
        self.assertEqual(len(parent._config._children), 1)
        self.assertEqual(len(parent.components_children._children), 2) # pyright: ignore[reportAttributeAccessIssue]

        child1.simple_prop += 1

        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
        self.assertTrue(parent.components_children[0].modified)

        parent.chain_syncronise()
        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)

        child3 = ChildComponent(name = 'child3')
        parent.components_children.append(child3)
        self.assertTrue(parent.modified)
        self.assertEqual(len(parent._config._children), 1)
        self.assertEqual(len(parent.components_children._children), 3) # pyright: ignore[reportAttributeAccessIssue]

        parent.chain_syncronise()

        child3.simple_prop += 1
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)

        parent.chain_syncronise()
        parent.components_children = []
        self.assertTrue(parent.modified)
        parent.chain_syncronise()

        child1.simple_prop += 1
        child2.simple_prop += 1
        child3.simple_prop += 1
        self.assertFalse(parent.chain_modified)

        child1.chain_syncronise()
        parent.components_children.insert(0, child1)
        self.assertTrue(parent.modified)
        parent.chain_syncronise()

        child1.simple_prop += 1
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)


    def test_ordereddict_creation_and_modification(self):
        child1 = ChildComponent(name = 'child1')
        child2 = ChildComponent(name = 'child2')

        parent = ParentOfOrderedDict(children = [child1, child2])

        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)
        self.assertEqual(len(parent._config._children), 1)
        self.assertEqual(len(parent.variables._children), 2) # pyright: ignore[reportAttributeAccessIssue]

        child1.simple_prop += 1
        
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
        self.assertTrue(list(parent.variables.values())[0].modified)

        parent.chain_syncronise()
        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)

        child3 = ChildComponent(name = 'child3')
        parent.variables['c3'] = child3
        self.assertTrue(parent.modified)
        self.assertEqual(len(parent._config._children), 1)
        self.assertEqual(len(parent.variables._children), 3) # pyright: ignore[reportAttributeAccessIssue]

        parent.chain_syncronise()
        
        child3.simple_prop += 1
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)

        parent.chain_syncronise()
        parent.variables = {}
        self.assertTrue(parent.modified)
        parent.chain_syncronise()

        child1.simple_prop += 1
        child2.simple_prop += 1
        child3.simple_prop += 1
        self.assertFalse(parent.chain_modified)

        child1.chain_syncronise()
        parent.variables['newid'] = child1
        self.assertTrue(parent.modified)
        parent.chain_syncronise()

        child1.simple_prop += 1
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
