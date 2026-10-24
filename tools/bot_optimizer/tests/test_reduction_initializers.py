import ast
import unittest

from tools.bot_optimizer.reduction_initializers import initialization_site


SOURCE = '''if miss:
    first = 0
    second = 0
    peak = None
    key = prepared_key
    value = cache.get(key, cache)
    if value is cache:
        for item in route:
            first += item
            second += item
            peak = item
        if builtin.len(cache) < 4096:
            cache[key] = (first, second, peak)
    else:
        first, second, peak = value
'''


class ReductionInitializerTests(unittest.TestCase):
    def test_intact_cache_and_contiguous_initializers(self):
        for mutation in ('none', 'initial', 'key', 'lookup', 'origin', 'hit', 'publish', 'effect', 'output-read'):
            tree = ast.parse(SOURCE)
            body = tree.body[0].body
            for n in body[:3]:
                n._bcopt_group_init = True
            body[3]._bcopt_group_key = True
            body[3].value._bcopt_integer_multiset_key = True
            body[4]._bcopt_group_lookup = True
            group = body[5]
            group.body[1]._bcopt_integer_cache_publish = True
            caches = {'cache'}
            if mutation == 'initial':
                body[0].value = ast.Constant(1)
            elif mutation == 'key':
                del body[3].value._bcopt_integer_multiset_key
            elif mutation == 'lookup':
                body[4].value.args[1] = ast.Constant(None)
            elif mutation == 'origin':
                caches = set()
            elif mutation == 'hit':
                group.orelse[0].targets[0].elts.reverse()
            elif mutation == 'publish':
                group.body[1].body.append(ast.parse('callback()').body[0])
            elif mutation == 'effect':
                body.insert(3, ast.parse('callback()').body[0])
            elif mutation == 'output-read':
                body[3].value.id = 'first'
            result = initialization_site(tree, group, ('first', 'second', 'peak'), caches)
            self.assertEqual(result is not None, mutation == 'none', mutation)


if __name__ == '__main__':
    unittest.main()
