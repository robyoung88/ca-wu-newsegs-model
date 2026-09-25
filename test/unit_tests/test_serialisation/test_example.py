"""
Unit tests for constructor example code
"""
import unittest



from newsegsmodelframework.core.serialisation import SerialiseToDictMixin

class TestRegistryExample(unittest.TestCase):
    def test_example_code(self):
        class A(SerialiseToDictMixin):
            _constructor_class = 'MetaA'

            param: int
            def __init__(self, param: int):
                self.param = param

            def __eq__(self, other):
                return self.param == other.param

        from newsegsmodelframework.core.constructors.registers import register_constructor_class
        @register_constructor_class('MetaA')
        def meta_a_constructors():
            return {'A': A}

        foo = A(5)
        foodict = foo.to_dict()

        from newsegsmodelframework.core import find_constructor
        bar = find_constructor(foodict['constructor_class'], foodict['class'])(foodict)

        self.assertEqual(type(foo), type(bar))
        self.assertEqual(foo, bar)
        