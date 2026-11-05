#!/usr/bin/env python3
"""Pi checks; all generated headers and binaries stay in a temporary directory."""
from pathlib import Path
import os
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"
ROOT = HERE.parents[2]
CXX = os.environ.get("CXX", "g++")


def run(args):
    result = subprocess.run([str(arg) for arg in args], text=True, capture_output=True)
    if result.returncode:
        print(result.stdout, end="")
        print(result.stderr, end="")
        result.check_returncode()
    print(result.stdout, end="")
    # GCC requires -fpermissive for the unchanged SDK's team() declarations.
    # Do not hide any other diagnostics.
    if result.stderr:
        print(result.stderr, end="")


def geometry_body(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end].replace("World::", "")


with tempfile.TemporaryDirectory(prefix="bce01-checks-") as directory:
    tmp = Path(directory)
    common = [CXX, "-std=c++20", "-O2", "-Wall", "-Wextra", "-I", SRC]
    run(common + [HERE / "decisions.cpp", SRC / "state_machine.cpp", "-o", tmp / "decisions"])
    run([tmp / "decisions"])
    geometry = (SRC / "objectives.cpp").read_text()
    (tmp / "geometry-under-test.h").write_text(
        "#pragma once\nnamespace lp { struct vec2 { int x,y; };\n"
        "struct World { int width,height,columns,rows;\n"
        + geometry_body(geometry, "int World::chunk(") + "\n"
        + geometry_body(geometry, "vec2 World::center(") + "\n}; }\n"
    )
    run(common + ["-I", tmp, HERE / "strategy_contracts.cpp", SRC / "state_machine.cpp",
                  "-o", tmp / "contracts"])
    run([tmp / "contracts"])
    sdk = ["-fpermissive", "-include", "cmath", "-I", ROOT / "sdk/cpp"]
    run(common + sdk + ["-ffunction-sections", "-fdata-sections", HERE / "bank_escape.cpp",
                        SRC / "economy.cpp", "-Wl,--gc-sections", "-o", tmp / "bank_escape"])
    run([tmp / "bank_escape"])
    run([CXX, "-std=c++20"] + sdk + ["-fsyntax-only"] + sorted(SRC.glob("*.cpp")))
    print("PASS real-SDK syntax checks for all production translation units")
