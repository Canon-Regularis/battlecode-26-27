import io
import unittest
import numpy as np
from .reference import ranges


class ReferenceRows(unittest.TestCase):
    def stream(self, value):
        stream = io.BytesIO(); np.save(stream, value); stream.seek(0); return stream

    def test_exact_noncontiguous_ranges(self):
        original = np.arange(90, dtype=np.float16).reshape(10,3,3)
        got = dict(ranges(self.stream(original), [('b',7,2), ('a',1,3)]))
        np.testing.assert_array_equal(got['a'], original[1:4])
        np.testing.assert_array_equal(got['b'], original[7:9])

    def test_overlaps_and_truncation_rejected(self):
        with self.assertRaises(ValueError):
            list(ranges(self.stream(np.arange(10)), [('a',1,4),('b',3,2)]))
        stream=self.stream(np.arange(10)); data=stream.getvalue()[:-8]
        with self.assertRaises(ValueError): list(ranges(io.BytesIO(data), [('a',9,1)]))


if __name__ == '__main__': unittest.main()
