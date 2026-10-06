"""Ensure that components are getting revised correctly when complex children are modified.
"""
import copy
from dataclasses import field
import pickle

from typing import Any, Sequence, override
import unittest

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.trackeddata import ComponentProperty, DataWithRevision, ObservableList, revision_dataclass, IMMUTABLE_TYPES
from newsegsmodelframework.core.constructors import registers

@revision_dataclass
class ChildConfig(DataWithRevision):
    simple_prop: int = 0
    list_prop: list[Any] = field(default_factory=list)
    obj_prop: dict[str, Any] = field(default_factory=dict)

@revision_dataclass
class DummyConfig(DataWithRevision):
    ...

class DummyChildComponent(NewsegsComponent):
    
    @override
    def _generate_config(self, *args, **kwargs) -> ChildConfig:
        return ChildConfig(*args, **kwargs)
    _config: ChildConfig # pyright: ignore[reportIncompatibleVariableOverride]


class DummyParentComponent(NewsegsComponent):

    @override
    def _generate_config(self, *args, **kwargs) -> DummyConfig:
        return DummyConfig(*args, **kwargs)
    _config: DummyConfig # pyright: ignore[reportIncompatibleVariableOverride]

    child = ComponentProperty(oftype = DummyChildComponent)

    def __init__(
        self,
        *args,
        child: DummyChildComponent,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.child = child
        self.revision = 0

# DummyParentComponent._excluded_attributes = super(DummyParentComponent, DummyParentComponent)._excluded_attributes + (
#     '_child',
# )

registers.register_custom_class(ChildConfig._constructor_class, ChildConfig)
registers.register_custom_class(DummyChildComponent._constructor_class, DummyChildComponent)
registers.register_custom_class(DummyConfig._constructor_class, DummyConfig)
registers.register_custom_class(DummyParentComponent._constructor_class, DummyParentComponent)

class TestChildComponentRevisions(unittest.TestCase):

    def test_observable_list_subscription(self):
        child = DummyChildComponent(
            name = 'child1', 
            simple_prop = 1, 
            obj_prop = {'foo': 'bar'}
        )

        def list_modifications(obj:DummyChildComponent, val, expect_wrapped = False, msg: str|None = None):
            if msg is None:
                msg = str(type(val))
            
            self.assertFalse(obj.modified)
            self.assertFalse(obj.chain_modified)
            
            # Append
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)
            
            obj.list_prop.append(val)

            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.list_prop), l0 + 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top + 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list + 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)

            # Insert
            val_insert = copy.deepcopy(val)
            obj.list_prop.insert(0, val_insert)

            if not expect_wrapped:
                self.assertIs(obj.list_prop[0], val_insert, msg)
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.list_prop), l0 + 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top + 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list + 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)
            
            # Pop
            recovered_val_insert = obj.list_prop.pop(0)

            if not expect_wrapped:
                self.assertIs(recovered_val_insert, val_insert, msg)
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.list_prop), l0 - 1, msg)

            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top - 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list - 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)

            # Remove
            obj.list_prop.remove(val)
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.list_prop), l0 - 1, msg)

            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top - 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list - 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.list_prop._children), obs_list, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)

            # Extend
            if isinstance(val, Sequence):
                val_len = len(val)
                obj.list_prop.extend(val)

                self.assertTrue(obj.modified, msg)
                self.assertEqual(obj.revision, r0 + 1, msg)
                self.assertEqual(len(obj.list_prop), l0 + val_len, msg)

            
            # Ensure we have contents before testing clear
            obj.list_prop.append(val)
            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.list_prop)
            obs_top = len(obj._config._children)
            obs_list = len(obj.list_prop._children)

            # Clear
            obj.list_prop.clear()
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.list_prop), 0, msg)
            self.assertEqual(len(obj.list_prop._children), 0, msg)
            #self.assertEqual(len(obj._config._children), obs_top - obs_list)
            self.assertEqual(len(obj._config._children), obs_top)

            obj.chain_syncronise()

        # Simple type
        list_modifications(child, 4.0)
        list_modifications(child, 'foo')

        # List
        list_modifications(child, [1, 2, 3], True)

        # Dict
        list_modifications(child, {'alpha': 0, 'beta': 1}, True)

        # Iterable
        list_modifications(child, ('a', 'b', 'c'), False)

        # Component
        newchild = DummyChildComponent(name = 'child2', simple_prop = 10)
        list_modifications(child, newchild, True)


    def test_observable_dict_subscription(self):
        child = DummyChildComponent(
            name = 'child1', 
            simple_prop = 1, 
            obj_prop = {}
        )

        def dict_modifications(
            obj: DummyChildComponent,
            val,
            expect_wrapped = False,
            msg: str|None = None
        ):
            if msg is None:
                msg = str(type(val))

            self.assertFalse(obj.modified)
            self.assertFalse(obj.chain_modified)

            # Set item
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)
            
            obj.obj_prop['_dummy_'] = val
            
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.obj_prop), l0 + 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top + 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict + 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)

            # Update
            val_update = copy.deepcopy(val)
            obj.obj_prop.update({'_updated_': val_update})
            
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.obj_prop), l0 + 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top + 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict + 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)

            # Replacement
            val_replace = copy.deepcopy(val)
            obj.obj_prop['_dummy_'] = val_replace

            # Modification will not happen if not object
            if not isinstance(val, IMMUTABLE_TYPES):
                self.assertTrue(obj.modified, msg)
                self.assertEqual(obj.revision, r0 + 1, msg)
            else:
                self.assertFalse(obj.modified, msg)
                self.assertEqual(obj.revision, r0, msg)
            self.assertEqual(len(obj.obj_prop), l0, msg)
            if expect_wrapped:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)

            # Pop
            recovered_val_update = obj.obj_prop.pop('_updated_')
            if not expect_wrapped:
                self.assertIs(recovered_val_update, val_update, msg)

            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.obj_prop), l0 - 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top - 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict - 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)

            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)

            # Delete
            del obj.obj_prop['_dummy_']
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.obj_prop), l0 - 1, msg)
            if expect_wrapped:
                #self.assertEqual(len(obj._config._children), obs_top - 1, msg)
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict - 1, msg)
            else:
                self.assertEqual(len(obj._config._children), obs_top, msg)
                self.assertEqual(len(obj.obj_prop._children), obs_dict, msg)

            # Ensure we have contents before testing clear
            obj.obj_prop['_dummy_'] = val
            obj.chain_syncronise()
            r0 = obj.revision
            l0 = len(obj.obj_prop)
            obs_top = len(obj._config._children)
            obs_dict = len(obj.obj_prop._children)

            # Clear
            obj.obj_prop.clear()
            self.assertTrue(obj.modified, msg)
            self.assertEqual(obj.revision, r0 + 1, msg)
            self.assertEqual(len(obj.obj_prop), 0, msg)
            self.assertEqual(len(obj.obj_prop._children), 0, msg)
            #self.assertEqual(len(obj._config._children), obs_top - obs_dict, msg)
            self.assertEqual(len(obj._config._children), obs_top, msg)

            obj.chain_syncronise()

        # Simple type
        dict_modifications(child, 4.0)
        dict_modifications(child, 'foo')

        # List
        dict_modifications(child, [1, 2, 3], True)

        # Dict
        dict_modifications(child, {'alpha': 0, 'beta': 1}, True)

        # Iterable
        dict_modifications(child, ('a', 'b', 'c'), False)

        # Component
        newchild = DummyChildComponent(name = 'child2', simple_prop = 10)
        dict_modifications(child, newchild, True)

        # Replace property
        self.assertFalse(child.modified)
        self.assertFalse(child.chain_modified)
        child.obj_prop = {'new': 'dict'}
        self.assertTrue(child.modified)
        self.assertTrue(child.chain_modified)
        child.syncronise()

        dict_modifications(child, [1, 2, 3], True, 'Replaced dict, valuing with list')
            
    def test_chained_observables(self):
        child = DummyChildComponent(
            name = 'child1', 
            simple_prop = 1, 
            obj_prop = {'sublist': []}
        )

        self.assertFalse(child.modified)
        self.assertFalse(child.chain_modified)
        r0 = child.revision

        # Append sublist
        child.obj_prop['sublist'].append({'key': 'value'})

        self.assertTrue(child.modified)
        self.assertEqual(child.revision, r0 + 1)
        
        child.chain_syncronise()

        r0 = child.revision
        # Modify end of chain
        child.obj_prop['sublist'][0]['key'] = 4
        self.assertTrue(child.modified)
        self.assertEqual(child.revision, r0 + 1)

    def test_multiple_subscribers(self):
        child1 = DummyChildComponent(
            name = 'child1',
            simple_prop = 1
        )
        child2 = DummyChildComponent(
            name = 'child2',
            simple_prop = 1
        )

        mylist: ObservableList = ObservableList([1, 2, 3])
        child1.list_prop = mylist
        child2.list_prop = mylist
        child1.chain_syncronise()
        child2.chain_syncronise()

        # Modification affects both
        mylist.append(4)
        self.assertTrue(child1.modified)
        self.assertTrue(child2.modified)

        # Syncronising does not affect both
        child1.chain_syncronise()
        self.assertFalse(child1.modified)
        self.assertTrue(child2.modified)

        child2.chain_syncronise()

        # Adding a subchild affects both
        mylist.append({'key': 'value'})
        self.assertTrue(child1.modified)
        self.assertTrue(child2.modified)
        
        child1.chain_syncronise()
        child2.chain_syncronise()

        # Modifying subchild affects both
        child1.list_prop[4]['key'] = 'hole' 

        self.assertTrue(child1.modified)
        self.assertTrue(child2.modified)

        child1.chain_syncronise()
        child2.chain_syncronise()

        # replacing one does not affect other
        child1.list_prop = ObservableList(['a', 'b', 'c'])
        self.assertTrue(child1.modified)
        self.assertFalse(child2.modified)
        self.assertEqual(len(child1._config._children), len(child2._config._children))

        child1.chain_syncronise()
        child2.chain_syncronise()
        
        child1.list_prop.append('d')
        self.assertTrue(child1.modified)
        self.assertFalse(child2.modified)

        child1.chain_syncronise()
        child2.chain_syncronise()

        mylist[4]['new_key'] = 123
        self.assertFalse(child1.modified)
        self.assertTrue(child2.modified)


    def test_single_child_revisions(self):
        child = DummyChildComponent(name = 'child1', simple_prop = 1, obj_prop = {'foo': 'bar'})
        parent = DummyParentComponent(name = 'parent1', child = child)

        r0_p = parent.revision
        r0_c = child.revision
        self.assertFalse(parent.modified)
        self.assertFalse(child.modified)
        self.assertFalse(parent.chain_modified)
        self.assertTrue(len(parent._config._children), 1)
        self.assertTrue(len(child._config._children), 1)

        child.simple_prop = 2
        self.assertTrue(child.modified)
        self.assertEqual(child.revision, r0_c + 1)
        self.assertTrue(parent.modified) # Subscription works!
        self.assertTrue(parent.chain_modified)
        
        parent.chain_syncronise()
        self.assertFalse(child.modified)
        self.assertFalse(parent.chain_modified)

        child.obj_prop['alice'] = 'bob'
        self.assertTrue(child.modified)
        self.assertEqual(child.revision, r0_c + 2)
        self.assertTrue(len(child._config._children), 2)
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
        
        parent.chain_syncronise()
        self.assertFalse(child.modified)
        self.assertFalse(parent.chain_modified)

        child.obj_prop['newdict'] = {'spam': 'eggs'}
        self.assertTrue(child.modified)
        self.assertEqual(child.revision, r0_c + 3)
        self.assertTrue(len(child._config._children), 3)
        self.assertTrue(parent.modified)
        self.assertTrue(parent.chain_modified)
        
        parent.chain_syncronise()
        self.assertFalse(child.modified)
        self.assertFalse(parent.chain_modified)

        newchild = DummyChildComponent(name = 'child2', simple_prop = 10, obj_prop = {'x': 'y'})
        parent.child = newchild
        self.assertFalse(parent.child.modified)
        self.assertTrue(parent.modified)
        self.assertEqual(parent.revision, r0_p + 4)
        self.assertTrue(len(parent._config._children), 1)

        parent.chain_syncronise()

        child.simple_prop = 3
        self.assertTrue(child.modified)
        self.assertFalse(parent.chain_modified)

    def test_serialisation(self):
        child_0 = DummyChildComponent(
            name = 'child 0',
            simple_prop = 10,
            obj_prop = {'foo': 'bar'},
            list_prop = [1, 2, 3]
        )

        srl = pickle.dumps(child_0)

        child_1 = pickle.loads(srl)

        # Check all instances new
        self.assertFalse(child_1 is child_0)
        self.assertFalse(child_1.obj_prop is child_0.obj_prop)
        self.assertFalse(child_1.list_prop is child_0.list_prop)

        # Check value equality
        self.assertEqual(child_0.name, child_1.name)
        self.assertEqual(child_0.simple_prop, child_1.simple_prop)
        self.assertEqual(child_0.obj_prop, child_1.obj_prop)
        self.assertEqual(child_0.list_prop, child_1.list_prop)
        self.assertEqual(child_0.revision, child_1.revision)

        # Check child status
        self.assertEqual(len(child_0._config._children), len(child_1._config._children))
        for idx, child in enumerate(child_0._config._children):
            self.assertFalse(child_1._config._children[idx] is child)

        # Check subscriber status
        self.assertEqual(len(child_0.list_prop._subscribers), len(child_1.list_prop._subscribers))
        for idx, subscriber in enumerate(child_0.list_prop._subscribers):
            self.assertFalse(child_1.list_prop._subscribers[idx] is subscriber)

        self.assertEqual(len(child_0.obj_prop._subscribers), len(child_1.obj_prop._subscribers))
        for idx, subscriber in enumerate(child_0.obj_prop._subscribers):
            self.assertFalse(child_1.obj_prop._subscribers[idx] is subscriber)

        # Check revision independence

        # Should be impossible for the simple prop to cause issues, but for completeness:
        child_1.simple_prop += 1
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()


        child_1.list_prop.append(4)
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

        child_1.obj_prop['spam'] = 'eggs'
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

    def test_shallow_copy(self):
        child_0 = DummyChildComponent(
            name = 'child 0',
            simple_prop = 10,
            obj_prop = {'foo': 'bar'},
            list_prop = [1, 2, 3]
        )

        child_1 = copy.copy(child_0)

        # Check instance expectation
        self.assertFalse(child_1 is child_0)
        self.assertTrue(child_1.obj_prop is child_0.obj_prop)
        self.assertTrue(child_1.list_prop is child_0.list_prop)

        # Check value equality
        self.assertEqual(child_0.name, child_1.name)
        self.assertEqual(child_0.simple_prop, child_1.simple_prop)
        self.assertEqual(child_0.obj_prop, child_1.obj_prop)
        self.assertEqual(child_0.list_prop, child_1.list_prop)
        self.assertEqual(child_0.revision, child_1.revision)

        # Check child status
        self.assertEqual(len(child_0._config._children), len(child_1._config._children))
        for idx, child in enumerate(child_0._config._children):
            self.assertTrue(child_1._config._children[idx] is child)

        # Check subscriber status
        self.assertEqual(len(child_0.list_prop._subscribers), len(child_1.list_prop._subscribers))
        for idx, subscriber in enumerate(child_0.list_prop._subscribers):
            self.assertTrue(child_1.list_prop._subscribers[idx] is subscriber)

        self.assertEqual(len(child_0.obj_prop._subscribers), len(child_1.obj_prop._subscribers))
        for idx, subscriber in enumerate(child_0.obj_prop._subscribers):
            self.assertTrue(child_1.obj_prop._subscribers[idx] is subscriber)

        # Check revision dependence
        # Simple prop will not carry
        child_1.simple_prop += 1
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

        # List prop should affect both
        child_1.list_prop.append(4)
        self.assertTrue(child_0.modified)
        self.assertTrue(child_1.modified)
        child_0.chain_syncronise()
        child_1.chain_syncronise()

        # Dict prop should affect both
        child_1.obj_prop['spam'] = 'eggs'
        self.assertTrue(child_0.modified)
        self.assertTrue(child_1.modified)
        child_0.chain_syncronise()
        child_1.chain_syncronise()

        # Check true both ways
        child_0.obj_prop['spam'] = 'hame'
        self.assertTrue(child_0.modified)
        self.assertTrue(child_1.modified)
        child_0.chain_syncronise()
        child_1.chain_syncronise()

    def test_deep_copy(self):
        child_0 = DummyChildComponent(
            name = 'child 0',
            simple_prop = 10,
            obj_prop = {'foo': 'bar'},
            list_prop = [1, 2, 3]
        )

        child_1 = copy.deepcopy(child_0)

        # Check all instances new
        self.assertFalse(child_1 is child_0)
        self.assertFalse(child_1.obj_prop is child_0.obj_prop)
        self.assertFalse(child_1.list_prop is child_0.list_prop)

        # Check value equality
        self.assertEqual(child_0.name, child_1.name)
        self.assertEqual(child_0.simple_prop, child_1.simple_prop)
        self.assertEqual(child_0.obj_prop, child_1.obj_prop)
        self.assertEqual(child_0.list_prop, child_1.list_prop)
        self.assertEqual(child_0.revision, child_1.revision)

        # Check child status
        self.assertEqual(len(child_0._config._children), len(child_1._config._children))
        for idx, child in enumerate(child_0._config._children):
            self.assertFalse(child_1._config._children[idx] is child)

        # Check subscriber status
        self.assertEqual(len(child_0.list_prop._subscribers), len(child_1.list_prop._subscribers))
        for idx, subscriber in enumerate(child_0.list_prop._subscribers):
            self.assertFalse(child_1.list_prop._subscribers[idx] is subscriber)

        self.assertEqual(len(child_0.obj_prop._subscribers), len(child_1.obj_prop._subscribers))
        for idx, subscriber in enumerate(child_0.obj_prop._subscribers):
            self.assertFalse(child_1.obj_prop._subscribers[idx] is subscriber)

        # Check revision independence

        # Should be impossible for the simple prop to cause issues, but for completeness:
        child_1.simple_prop += 1
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()


        child_1.list_prop.append(4)
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

        child_1.obj_prop['spam'] = 'eggs'
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

    def test_dictionary_reconstruction(self):
        child_0 = DummyChildComponent(
            name = 'child 0',
            simple_prop = 10,
            obj_prop = {'foo': 'bar'},
            list_prop = [1, 2, 3]
        )

        # Standard (i.e. components not included - not relevant for this object anyway)
        d1 = child_0.to_dict()

        child_1 = DummyChildComponent.from_dict(d1)

        # Check all instances new
        self.assertFalse(child_1 is child_0)
        self.assertFalse(child_1.obj_prop is child_0.obj_prop)
        self.assertFalse(child_1.list_prop is child_0.list_prop)

        # Check value equality
        self.assertEqual(child_0.name, child_1.name)
        self.assertEqual(child_0.simple_prop, child_1.simple_prop)
        self.assertEqual(child_0.obj_prop, child_1.obj_prop)
        self.assertEqual(child_0.list_prop, child_1.list_prop)
        self.assertEqual(child_0.revision, child_1.revision)

        # Check child status
        self.assertEqual(len(child_0._config._children), len(child_1._config._children))
        for idx, child in enumerate(child_0._config._children):
            self.assertFalse(child_1._config._children[idx] is child)

        # Check subscriber status
        self.assertEqual(len(child_0.list_prop._subscribers), len(child_1.list_prop._subscribers))
        for idx, subscriber in enumerate(child_0.list_prop._subscribers):
            self.assertFalse(child_1.list_prop._subscribers[idx] is subscriber)

        self.assertEqual(len(child_0.obj_prop._subscribers), len(child_1.obj_prop._subscribers))
        for idx, subscriber in enumerate(child_0.obj_prop._subscribers):
            self.assertFalse(child_1.obj_prop._subscribers[idx] is subscriber)

        # Check revision independence

        # Should be impossible for the simple prop to cause issues, but for completeness:
        child_1.simple_prop += 1
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()


        child_1.list_prop.append(4)
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()

        child_1.obj_prop['spam'] = 'eggs'
        self.assertFalse(child_0.modified)
        self.assertTrue(child_1.modified)
        child_1.chain_syncronise()
