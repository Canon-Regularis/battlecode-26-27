import ast
import json
from pathlib import Path
import sys
import tempfile
import textwrap
from types import ModuleType
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_folder, optimize_source


def execute(source):
    module = ModuleType("_optimizer_specialization_test")
    with patch.dict(sys.modules, {module.__name__: module}):
        exec(compile(source, "<fixture>", "exec"), module.__dict__)
    return module.__dict__


class SpecializationTests(unittest.TestCase):
    def transform(self, source, options=None):
        source = textwrap.dedent(source)
        return source, optimize_source(source, options)

    def compare(self, source, inputs=((),), options=None):
        source, result = self.transform(source, options)
        old, new = execute(source), execute(result.source)
        for args in inputs:
            self.assertEqual(old["run"](*args), new["run"](*args))
        return result

    def test_keyword_binding_preserves_argument_order_and_keyword_only(self):
        result = self.compare("""
            def combine(a, b, *, tag):
                return a, b, tag
            def run():
                seen = []
                def touch(x):
                    seen.append(x)
                    return x
                result = combine(a=touch(1), b=touch(2), tag=touch(3))
                return result, seen
        """)
        self.assertIn("call-positional", [c.pass_name for c in result.changes])
        self.assertIn("combine(touch(1), touch(2), tag=touch(3))", result.source)

    def test_keyword_order_default_holes_varargs_and_invalid_calls_not_repaired(self):
        declarations = "def target(a=1, b=2, /, c=3, *, d=4):\n    return a,b,c,d\n"
        for call in ("target(a=5)", "target(1, c=3)", "target(1, 2, c=3, unknown=5)",
                     "target(1, 2, 3, c=4)", "target(c=5, d=6)"):
            _, result = self.transform(declarations + f"def run():\n    return {call}")
            self.assertNotIn("call-positional", [c.pass_name for c in result.changes])
        result = self.compare("""
            def target(a, b):
                return a, b
            def run():
                return target(b=2, a=1)
        """)
        self.assertFalse(result.changes)
        _, result = self.transform("def target(a, **kw):\n    return a,kw\ndef run():\n    return target(a=1,b=2)")
        self.assertFalse(result.changes)

    def test_shadowed_decorated_inherited_or_custom_new_calls_unknown(self):
        for source in ("""
            def target(a, b):
                return a,b
            def run(target):
                return target(a=1,b=2)
        """, """
            def deco(fn):
                return lambda **kw: kw
            @deco
            def target(a, b):
                return a,b
            def run():
                return target(a=1,b=2)
        """, """
            class Target:
                __new__ = staticmethod(lambda *args, **kw: object.__new__(Target))
                def __init__(self, a, b):
                    pass
            def run():
                return Target(a=1,b=2)
        """):
            _, result = self.transform(source)
            self.assertNotIn("call-positional", [c.pass_name for c in result.changes])

    def test_identity_generators_stream_custom_iterables_without_length_hint(self):
        source = """
            def run():
                seen = []
                class Values:
                    def __iter__(self):
                        seen.append('iter')
                        return iter([3, 0, 5])
                    def __len__(self):
                        raise AssertionError('length hint must not be called')
                return (sum(x for x in Values()), min(x for x in Values()),
                        max(x for x in Values()), any(x for x in Values()),
                        all(x for x in Values()), seen)
        """
        result = self.compare(source)
        self.assertEqual(sum(c.pass_name == "identity-reduction" for c in result.changes), 5)

    def test_identity_sum_preserves_custom_addition_interleaving(self):
        self.compare("""
            def run():
                seen=[]
                class Value:
                    def __radd__(self, left):
                        seen.append('add')
                        return 0
                def values():
                    for _ in range(3):
                        seen.append('next')
                        yield Value()
                result=sum(x for x in values())
                return result,seen
        """)

    def test_identity_consumers_with_length_hints_or_effectful_kwargs_untouched(self):
        for expression in ("list(x for x in values)", "tuple(x for x in values)",
                           "sorted(x for x in values)", "sum((x for x in values), start=f())",
                           "min((x for x in values), default=f())", "sum(x for x in values if x)"):
            _, result = self.transform(f"def run(values,f):\n    return {expression}")
            self.assertNotIn("identity-reduction", [c.pass_name for c in result.changes])

    def test_bounded_tuple_reductions(self):
        result = self.compare("""
            def run():
                values=tuple(range(16))
                return sum(x*x for x in values), min(x*x for x in values), max(x*x for x in values)
        """)
        self.assertEqual(sum(c.pass_name == "bounded-reduction" for c in result.changes), 3)

    def test_unknown_length_tuple_guard_and_fallback(self):
        result = self.compare("def run(values: tuple[int,...]):\n    return sum(x*x for x in values)",
                              [((),), ((1,2),), (tuple(range(20)),)],
                              Options(trust_annotations=True, max_materialize=4))
        self.assertIn("len(values) <= 4", result.source)
        self.assertIn("else sum((", result.source)

    def test_mutable_unknown_starred_float_tuples_not_materialized(self):
        for expression in ("[1,2,3]", "(1.1,2.2)", "(*unknown,)"):
            _, result = self.transform(f"def run(unknown):\n    values={expression}\n    return sum(x*x for x in values)")
            self.assertNotIn("bounded-reduction", [c.pass_name for c in result.changes])

    def test_integer_helpers_inline_only_with_proven_inputs(self):
        result = self.compare("""
            def square(x):
                return x*x
            def mixed(a,b):
                return a*3-b
            def run(n):
                total=0
                for i in range(n):
                    total += square(i) + mixed(i,2)
                return total
        """, [(0,), (1,), (100,)])
        self.assertEqual(sum(c.pass_name == "inline-integer-helper" for c in result.changes), 2)

    def test_helper_unknown_effectful_or_late_bound_not_inlined(self):
        for source in ("""
            def square(x):
                return x*x
            def run(x):
                return square(x)
        """, """
            def run():
                return square(3)
            def square(x):
                return x*x
        """, """
            def square(x):
                print(x)
                return x*x
            def run():
                return square(3)
        """):
            _, result = self.transform(source)
            self.assertNotIn("inline-integer-helper", [c.pass_name for c in result.changes])

    def test_bulk_frozen_record_preserves_type_equality_hash_fields_and_freezing(self):
        source, result = self.transform("""
            from __future__ import annotations
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Sample:
                a:int
                b:int
                c:int
                d:int
            def run():
                obj=Sample(1,2,3,4)
                return repr(obj),hash(obj),obj==Sample(1,2,3,4)
        """)
        old, new = execute(source), execute(result.source)
        self.assertEqual(old['run'](),new['run']())
        self.assertIn("record-bulk-init", [c.pass_name for c in result.changes])
        self.assertEqual(old['Sample'].__init__.__annotations__,new['Sample'].__init__.__annotations__)
        self.assertEqual(old['Sample'].__doc__,new['Sample'].__doc__)
        for namespace in (old,new):
            instance=namespace['Sample'](1,2,3,4)
            with self.assertRaises(AttributeError):
                instance.a=9

    def test_bulk_record_subclass_descriptor_fallback(self):
        result = self.compare("""
            from dataclasses import dataclass
            seen=[]
            @dataclass(frozen=True)
            class Sample:
                a:int
                b:int
                c:int
                d:int
            class Sub(Sample):
                @property
                def a(self):
                    return self._a
                @a.setter
                def a(self,value):
                    seen.append(value)
                    object.__setattr__(self,'_a',value)
            def run():
                obj=Sub(1,2,3,4)
                return obj.a,obj.b,seen
        """)
        self.assertIn("record-bulk-init", [c.pass_name for c in result.changes])

    def test_record_defaults_factories_slots_hooks_and_bases_not_bulk_optimised(self):
        for fields, decorator, extra in (
            ("a:int=1\nb:int=2\nc:int=3\nd:int=4", "frozen=True", ""),
            ("a:int\nb:int\nc:int\nd:int", "frozen=True,slots=True", ""),
            ("a:int\nb:int\nc:int\nd:int", "frozen=True", "def __post_init__(self):\n    pass"),
            ("a:int\nb:int\nc:int\nd:int", "frozen=False", ""),
        ):
            source = (f"from dataclasses import dataclass\n@dataclass({decorator})\nclass Sample:\n"
                      + textwrap.indent(fields + ('\n'+extra if extra else ''),'    '))
            _, result = self.transform(source)
            self.assertNotIn("record-bulk-init", [c.pass_name for c in result.changes])

    def test_aliased_special_dataclass_annotations_do_not_guess_a_record_layout(self):
        for special, imports in (('ClassVar','from typing import ClassVar'),
                                 ('InitVar','from dataclasses import InitVar'),
                                 ('KW_ONLY','from dataclasses import KW_ONLY')):
            _, result = self.transform(f"""
                from dataclasses import dataclass
                {imports}
                Alias={special}
                @dataclass(frozen=True)
                class Sample:
                    a:Alias
                    b:int
                    c:int
                    d:int
                def run():
                    return Sample(a=1,b=2,c=3,d=4)
            """)
            self.assertNotIn('record-bulk-init',[c.pass_name for c in result.changes])
            self.assertNotIn('call-positional',[c.pass_name for c in result.changes])
        _,result=self.transform("""
            from dataclasses import dataclass
            from typing import ClassVar
            int=ClassVar
            @dataclass(frozen=True)
            class Sample:
                a:int
                b:float
                c:float
                d:float
        """)
        self.assertNotIn('record-bulk-init',[c.pass_name for c in result.changes])

    def test_scalar_record_keeps_primitive_value_semantics(self):
        result = self.compare("""
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Point:
                x:int
                y:int
            def run():
                base=3
                temporary=Point(x=base*base,y=5)
                return temporary.x*temporary.x + temporary.y
        """)
        self.assertIn("scalar-record", [c.pass_name for c in result.changes])
        self.assertNotIn("temporary = Point", result.source)

    def test_scalar_record_captures_unknown_objects_and_other_escapes_not_eliminated(self):
        prefix = "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Point:\n    x:object\n    y:object\n"
        for body in ("temporary=Point(x,y)\nreturn temporary.x", "temporary=Point(1,2)\nreturn temporary",
                     "temporary=Point(1,2)\nreturn lambda: temporary.x", "temporary=Point(1,2)\nreturn type(temporary)"):
            _, result = self.transform(prefix + "def run(x,y):\n" + textwrap.indent(body,"    "))
            self.assertNotIn("scalar-record", [c.pass_name for c in result.changes])

    def test_scalar_shadowed_builtin_cannot_prove_field_primitive(self):
        _, result = self.transform("""
            from dataclasses import dataclass
            @dataclass
            class Point:
                x:object
                y:object
            def run(abs):
                temporary=Point(abs(1),2)
                return temporary.x
        """)
        self.assertNotIn("scalar-record", [c.pass_name for c in result.changes])

    def test_callable_mutation_deoptimises(self):
        _, result = self.transform("""
            def square(x):
                return x*x
            alias=square
            alias.__defaults__=(2,)
            def run():
                return square(x=3)
        """)
        self.assertFalse(result.changes)
        self.assertTrue(result.warnings)

    def test_record_namespace_descriptor_mutation_and_aliases_deoptimise(self):
        for target, alias in (('Sample',''),('alias','alias=Sample\n')):
            _,result=self.transform("from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Sample:\n    a:int\n    b:int\n    c:int\n    d:int\n"
                                   +alias+f"{target}.a=property(lambda self:99)\n")
            self.assertFalse(result.changes)
            self.assertTrue(result.warnings)

    def test_replaced_initializer_inside_class_not_given_a_stale_signature(self):
        _, result = self.transform("""
            class Sample:
                def __init__(self,a,b):
                    pass
                __init__=lambda self,**kw: None
            def run():
                return Sample(a=1,b=2)
        """)
        self.assertNotIn('call-positional',[c.pass_name for c in result.changes])

    def test_class_name_mangling_does_not_resolve_a_different_global_callable(self):
        result=self.compare("""
            def __combine(a,b):
                return a,b
            def _Worker__combine(**kw):
                return kw
            def __square(x):
                return x*x
            def _Worker__square(x):
                return 999
            class Worker:
                def run(self):
                    x=3
                    return __combine(a=1,b=2),__square(x)
            def run():
                return Worker().run()
        """)
        self.assertNotIn('call-positional',[c.pass_name for c in result.changes])
        self.assertNotIn('inline-integer-helper',[c.pass_name for c in result.changes])

    def test_mangled_constructor_keyword_is_not_repaired(self):
        source,result=self.transform("""
            class Sample:
                def __init__(self,__value):
                    self.value=__value
            def run():
                return Sample(__value=3)
        """)
        for version in (source,result.source):
            with self.assertRaises(TypeError):
                execute(version)['run']()

    def test_private_keyword_helper_is_not_inlined(self):
        result=self.compare('def square(__value):\n    return __value*__value\ndef run():\n    return square(__value=3)')
        self.assertNotIn('inline-integer-helper',[c.pass_name for c in result.changes])

    def test_scalar_replacement_does_not_change_hidden_super_class_cell(self):
        result=self.compare("""
            from dataclasses import dataclass
            @dataclass
            class Pair:
                x:int
                y:int
            class Parent:
                pass
            class Worker(Parent):
                def method(self):
                    __class__=Pair(1,2)
                    return __class__.x,super()
            def run():
                try:
                    Worker().method()
                except Exception as error:
                    return type(error).__name__
                return 'no-error'
        """)
        self.assertNotIn('scalar-record',[c.pass_name for c in result.changes])

    def test_scalar_arguments_that_may_have_finalizers_are_kept(self):
        _, result = self.transform("""
            from dataclasses import dataclass
            @dataclass
            class Packet:
                a:object
                b:object
            def run(factory):
                temporary=Packet(factory(),factory())
                return temporary.a
        """)
        self.assertNotIn('scalar-record',[c.pass_name for c in result.changes])

    def test_scalar_record_preserves_unused_primitive_argument_exceptions(self):
        source, result = self.transform("""
            from dataclasses import dataclass
            @dataclass
            class Pair:
                a:int
                b:int
            def run():
                temporary=Pair(1,1//0)
                return temporary.a
        """)
        self.assertIn('scalar-record',[c.pass_name for c in result.changes])
        for version in (source,result.source):
            with self.assertRaises(ZeroDivisionError):
                execute(version)['run']()

    def test_other_bot_shaped_combat_scoring_uses_the_same_general_passes(self):
        result=self.compare("""
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class TargetScore:
                handle:int
                damage:int
                distance:int
                priority:int
            def weight(damage,distance):
                return damage*3-distance
            def run():
                scores=[]
                for index in range(12):
                    value=weight(index,2)
                    scores.append(TargetScore(handle=index,damage=index,distance=2,priority=value))
                return max(scores,key=lambda score:score.priority).handle
        """)
        passes={c.pass_name for c in result.changes}
        self.assertTrue({'record-bulk-init','call-positional','inline-integer-helper','native-attrgetter'}<=passes)

    def test_new_passes_disabled_and_emission_idempotent(self):
        source="def square(x):\n    return x*x\ndef run():\n    return square(x=3)"
        _, result=self.transform(source,Options(disabled=frozenset({'call-positional','inline-integer-helper'})))
        self.assertFalse(result.changes)
        _, result=self.transform(source)
        self.assertFalse(optimize_source(result.source).changes)


class CrossModuleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bot=self.root/'input'
        (self.bot/'src/pkg').mkdir(parents=True)
        (self.bot/'src/main.py').write_text('from pkg.consumer import run\n')
        (self.bot/'src/pkg/__init__.py').write_text('from .helpers import add\n')
        (self.bot/'src/pkg/helpers.py').write_text('def add(a,b):\n    return a+b\n')
        (self.bot/'src/pkg/consumer.py').write_text('from . import add\ndef run():\n    return add(a=3,b=4)\n')

    def test_package_relative_import_and_reexport_resolution(self):
        report=optimize_folder(self.bot,self.root/'output')
        self.assertEqual(report['pass_counts'],{'call-positional':1,'inline-integer-helper':1})
        output=(self.root/'output/src/pkg/consumer.py').read_text()
        self.assertIn('return 3 + 4',output)
        self.assertEqual(report['analysis']['modules'],4)

    def test_import_cycle_does_not_remove_callee_lookup(self):
        (self.bot/'src/pkg/helpers.py').write_text('from .consumer import run\ndef add(a,b):\n    return a+b\n')
        report=optimize_folder(self.bot,self.root/'output')
        self.assertNotIn('inline-integer-helper',report['pass_counts'])

    def test_cross_module_record_signature(self):
        (self.bot/'src/pkg/helpers.py').write_text('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Sample:\n    a:int\n    b:int\n')
        (self.bot/'src/pkg/consumer.py').write_text('from .helpers import Sample\ndef run():\n    return Sample(a=1,b=2)\n')
        report=optimize_folder(self.bot,self.root/'output')
        self.assertEqual(report['pass_counts'],{'record-inline-return':1})

    def test_custom_dataclasses_module_does_not_get_stdlib_contract(self):
        (self.bot/'src/dataclasses.py').write_text('def dataclass(**kw):\n    return lambda cls: cls\n')
        (self.bot/'src/pkg/helpers.py').write_text('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Sample:\n    a:int\n    b:int\n    c:int\n    d:int\n')
        report=optimize_folder(self.bot,self.root/'output')
        self.assertNotIn('record-bulk-init',report['pass_counts'])

    def test_dynamic_module_attributes_disable_cross_module_call_specialisation(self):
        (self.bot/'src/pkg/helpers.py').write_text('def __getattr__(name):\n    return lambda **kw: kw\ndef add(a,b):\n    return a+b\n')
        report=optimize_folder(self.bot,self.root/'output')
        self.assertNotIn('call-positional',report['pass_counts'])
        self.assertNotIn('inline-integer-helper',report['pass_counts'])
        self.assertTrue(report['analysis']['dynamic_module_attributes'])

    def test_private_module_attributes_are_not_resolved_through_class_mangling(self):
        (self.bot/'src/pkg/__init__.py').write_text('')
        (self.bot/'src/pkg/helpers.py').write_text('from dataclasses import dataclass\n@dataclass(frozen=True)\nclass __Sample:\n    a:int\n    b:int\ndef _Worker__Sample(**kw):\n    return kw\n')
        (self.bot/'src/pkg/consumer.py').write_text('from . import helpers\nclass Worker:\n    def run(self):\n        return helpers.__Sample(a=1,b=2)\ndef run():\n    return Worker().run()\n')
        report=optimize_folder(self.bot,self.root/'output')
        self.assertNotIn('call-positional',report['pass_counts'])


if __name__=='__main__':
    unittest.main()
