import copy
from dataclasses import field
from typing import Any, Optional, overload, override
import unittest

from useful_types import SequenceNotStr

from newsegsmodelframework.core.constructors import registers
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent, NewsegsComponentProviderInterface
from newsegsmodelframework.core.trackeddata import ComponentListProperty, ComponentOrderedDictProperty, ComponentProperty, DataWithRevision, revision_dataclass

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

class ParentOfProperties(NewsegsComponent):

    @override
    def _generate_config(self, *args, **kwargs) -> DummyConfig:
        return DummyConfig(*args, **kwargs)
    _config: DummyConfig # pyright: ignore[reportIncompatibleVariableOverride]

    prop_child_1 = ComponentProperty(default = ChildComponent, oftype = ChildComponent)
    prop_child_2 = ComponentProperty(default = None, oftype = ChildComponent)
    prop_child_3 = ComponentProperty(default = ChildComponent, oftype = ChildComponent)

    def __init__(
        self,
        *args,
        child1: Optional[ChildComponent] = None,
        child2: Optional[ChildComponent] = None,
        child3: Optional[ChildComponent] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        if child1:
            self.prop_child_1 = child1

        if child2:
            self.prop_child_2 = child2

        if child3:
            self.prop_child_3 = child3

        self.revision = 0

    # @override
    # def get_component_attributes(self) -> tuple[str, ...]:
    #     atts = super().get_component_attributes()
    #     return ('prop_child_1', 'prop_child_2', 'prop_child_3', *atts)

# ParentOfProperties._excluded_attributes = super(ParentOfProperties, ParentOfProperties)._excluded_attributes + (
#     '_prop_child_1', '_prop_child_2', '_prop_child_3',
# )



registers.register_custom_class(ChildConfig._constructor_class, ChildConfig)
registers.register_custom_class(ChildComponent._constructor_class, ChildComponent)
registers.register_custom_class(DummyConfig._constructor_class, DummyConfig)
registers.register_custom_class(ParentOfProperties._constructor_class, ParentOfProperties)


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

# ParentOfList._excluded_attributes = super(ParentOfList, ParentOfList)._excluded_attributes + (
#     '_components_children',
# )

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

# ParentOfOrderedDict._excluded_attributes = super(ParentOfOrderedDict, ParentOfOrderedDict)._excluded_attributes + (
#     '_variables',
# )


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

    def test_componentproperty_assignment(self):
        child1 = ChildComponent(name = 'child1')

        parent = ParentOfProperties(
            name = 'parent',
            child1 = child1,
        )

        self.assertEqual(parent.revision, 0)
        parent.chain_syncronise()
        self.assertFalse(parent.chain_modified)

        # Test access
        child_ids = {}
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            self.assertTrue(hasattr(parent, propname))
            cx = getattr(parent, propname)
            if idx != 2:
                self.assertIsInstance(cx, ChildComponent, propname)
            else:
                self.assertIsNone(cx, propname)
            child_ids[propname] = id(cx)

        # Check whether the syncronisation has persisted after creation of the default props
        self.assertFalse(parent.chain_modified)

        # Check that the props are being tracked
        # Because prop2 is still a default None, expect only 2 children
        self.assertEqual(len(parent._config._children), 2)
        
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent, propname)
            if idx != 2:
                self.assertEqual(len(cx._config._subscribers), 1, propname)

        # Check that the props are persistent
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent, propname)
            self.assertEqual(id(cx), child_ids[propname])

        # Check late bind works
        child2 = ChildComponent(name = 'child2')
        child_ids['prop_child_2'] = id(child2)
        parent.prop_child_2 = child2
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent, propname)
            self.assertEqual(id(cx), child_ids[propname])

        # Check that the change has been notified
        self.assertTrue(parent.modified)
        parent.chain_syncronise()

        # Check syncronisation is complete
        self.assertFalse(parent.modified)
        config_ids = set()
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent, propname)
            self.assertFalse(cx.modified)
            config_ids.add(id(cx._config))

        # Check children
        self.assertEqual(len(parent._config._children), 3)
        self.assertTrue(all(id(x) in config_ids for x in parent._config._children))

        # Check subscribers
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent, propname)
            self.assertEqual(len(cx._config._subscribers), 1, propname)
            self.assertIs(cx._config._subscribers[0], parent._config)

        # Check replacement works
        child3_0 = parent.prop_child_3
        child3_1 = ChildComponent(name = 'child3')
        self.assertEqual(len(child3_0._config._children), 2) # Don't forget its own two properties
        self.assertEqual(len(child3_0._config._subscribers), 1)
        self.assertEqual(len(child3_1._config._children), 2) # Don't forget its own two properties
        self.assertEqual(len(child3_1._config._subscribers), 0)

        parent.prop_child_3 = child3_1
        self.assertEqual(len(parent._config._children), 3)
        self.assertEqual(len(child3_0._config._children), 2)
        self.assertEqual(len(child3_0._config._subscribers), 0)
        self.assertEqual(len(child3_1._config._children), 2)
        self.assertEqual(len(child3_1._config._subscribers), 1)

        self.assertTrue(parent.modified)
        parent.chain_syncronise()
        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)

        child3_0.simple_prop += 1

        self.assertFalse(parent.modified)
        self.assertFalse(parent.chain_modified)

        child3_1.simple_prop += 1

        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)

        # Serialisation - expect children to be removed
        d1 = parent.to_dict()

        parent2 = ParentOfProperties.from_dict(d1)

        class CompProvider(NewsegsComponentProviderInterface):
            def __init__(
                self,
                comp_dict: dict
            ) -> None:
                self.comp_dict = comp_dict

            @overload
            def get_component(self, component_id: str) -> NewsegsComponent:
                ...
        
            @overload
            def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsComponent]:
                ...

            def get_component(
                self, 
                component_id: str | SequenceNotStr[str]
            ) -> NewsegsComponent | SequenceNotStr[NewsegsComponent]:
                if isinstance(component_id, str):
                    return self.comp_dict[component_id]
                else:
                    return[self.comp_dict[x] for x in component_id]

            def duplicate_component(
                self, 
                component_id: str | NewsegsComponent
            ) -> NewsegsComponent:
                if isinstance(component_id, str):
                    return copy.deepcopy(self.comp_dict[component_id])
                else:
                    return copy.deepcopy(component_id)

            def add_component(
                self,
                component: NewsegsComponent
            ) -> str:
                self.comp_dict[component.id] = component
                return component.id

            def get_default_component(
                self, 
                component_type: str, 
                index: int = -1
            ) -> NewsegsComponent:
                return next(iter(self.comp_dict.values()))
            
            def get_component_metadata(
                self, 
                component_id: str | SequenceNotStr[str], 
                metadata_ids: str | SequenceNotStr[str]
            ) -> dict[str, Any] | dict[str, dict[str, Any]]:
                return {'message': 'No metadata'}

            def set_component_metadata(
                self, component_id: str, metadata_id: str, metadata_value: Any
            ):
                ...

        provider = CompProvider(
            {
                child1.id: child1,
                child2.id: child2,
                child3_1.id: child3_1
            }
        )

        # Access a property prior to reattachment just to ensure that it is correctly replaced
        self.assertEqual(len(parent2.prop_child_3._config._subscribers), 1)

        # NB - by attaching components to this provider, we expect that they will NOT be removed
        # from their original parent.
        parent2.reattach_components(provider)

        child_ids['prop_child_3'] = id(child3_1)

        self.assertEqual(len(parent2._config._children), 3)
        for idx in range(1, 4):
            propname = f'prop_child_{idx}'
            cx = getattr(parent2, propname)
            self.assertEqual(id(cx), child_ids[propname], propname)
            self.assertEqual(len(cx._config._subscribers), 2, propname)
            self.assertIs(cx._config._subscribers[0], parent._config, propname)
            self.assertIs(cx._config._subscribers[1], parent2._config, propname)
            self.assertIn(cx._config, parent2._config._children, propname)
