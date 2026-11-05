"""Enforce the user's CPU policy: reserve one physical core, use the rest."""
from contextlib import contextmanager
import ctypes
import json
import os
import struct
import time


def limit_process():
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        handle = kernel.GetCurrentProcess()
        kernel.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        allowed, system = ctypes.c_size_t(), ctypes.c_size_t()
        if not kernel.GetProcessAffinityMask(handle, ctypes.byref(allowed), ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.GetLogicalProcessorInformationEx.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        length = ctypes.c_ulong()
        kernel.GetLogicalProcessorInformationEx(0, None, ctypes.byref(length))
        if not length.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(length.value)
        if not kernel.GetLogicalProcessorInformationEx(0, buffer, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        data = buffer.raw
        core_masks = []
        offset = 0
        while offset < length.value:
            relationship, size = struct.unpack_from('<II', data, offset)
            assert size >= 8, 'Invalid processor topology record'
            if relationship == 0:
                groups = struct.unpack_from('<H', data, offset + 30)[0]
                for group_index in range(groups):
                    base = offset + 32 + group_index * 16
                    mask, group = struct.unpack_from('<QH', data, base)
                    if group == 0:
                        core_masks.append(mask)
            offset += size
        assert core_masks, 'Cannot reserve a physical core without topology information'
        reserved = next(mask for mask in core_masks if mask & system.value)
        working = allowed.value & ~reserved
        if not working:
            raise RuntimeError('No permitted processor remains after reserving one physical core')
        if not kernel.SetProcessAffinityMask(handle, working):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.SetPriorityClass(handle, 0x4000):  # BELOW_NORMAL_PRIORITY_CLASS
            raise ctypes.WinError(ctypes.get_last_error())
        workers = working.bit_count()
        return dict(affinity_mask=working, reserved_core_mask=reserved,
                    physical_cores_in_group=len(core_masks), logical_cores=workers,
                    workers=workers, batch_size=120, cooldown_seconds=0,
                    summary_workers=workers, priority='BelowNormal')
    raise RuntimeError('The low-load policy must be implemented for this OS before running tests')


@contextmanager
def gentle_run(local):
    settings = limit_process()
    import msvcrt
    local.mkdir(parents=True, exist_ok=True)
    with (local / 'low-load.lock').open('a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        waiting = False
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if not waiting:
                    print('Waiting for the single low-load experiment slot', flush=True)
                    waiting = True
                time.sleep(10)
        try:
            print(f"CPU LIMIT: {settings['workers']} workers, one physical core reserved, BelowNormal", flush=True)
            (local / 'low-load-active.json').write_text(json.dumps(dict(
                pid=os.getpid(), **settings), indent=2) + '\n')
            yield settings
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
