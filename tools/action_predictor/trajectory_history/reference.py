"""Stream only eligible row ranges from large, hash-verified canonical arrays."""
import numpy as np
from numpy.lib import format


def header(stream):
    version = format.read_magic(stream)
    reader = {(1, 0): format.read_array_header_1_0, (2, 0): format.read_array_header_2_0}.get(version)
    if reader is None: raise ValueError('Unexpected NPY version')
    shape, fortran, dtype = reader(stream)
    if fortran or dtype.hasobject or not shape: raise ValueError('Expected row-major numeric array')
    return shape, dtype


def ranges(stream, selections):
    shape, dtype = header(stream)
    stride = int(np.prod(shape[1:]))*dtype.itemsize
    at = 0
    for key, start, count in sorted(selections, key=lambda s: s[1]):
        if start < at or start+count > shape[0]: raise ValueError('Overlapping/out-of-range reference selection')
        skip = (start-at)*stride
        while skip:
            chunk = stream.read(min(skip, 4*1024*1024))
            if not chunk: raise ValueError('Truncated reference array')
            skip -= len(chunk)
        block = stream.read(count*stride)
        if len(block) != count*stride: raise ValueError('Truncated reference rows')
        yield key, np.frombuffer(block, dtype=dtype).reshape((count, *shape[1:]))
        at = start+count
