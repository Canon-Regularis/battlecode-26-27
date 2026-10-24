"""Whole-folder driver. Never import or execute input bot code on the host."""

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tokenize

from .analysis import hazards
from .model import Options, SourceResult
from .passes import Rewriter
from .program import Program
from .records import RecordSpecializer
from .reductions import ShortReductions
from .shortcircuit import ShortCircuit
from .record_returns import InlineRecordReturns
from .extrema import ExtremumLoops
from .scalar_extrema import ScalarExtrema
from .adjacent import AdjacentPairs
from .extensions import AdjacentExtensions
from .tuple_insertions import TupleInsertions
from .helper_facts import HelperFacts, ReuseHelperFacts, StaticHelperShapes
from .regions import NumericRegions, finish_numeric_regions
from .numeric_ops import NumericOperations
from .entry_inlining import InlineNumericEntries
from .insertion_keys import InsertionKeys
from .incremental_edges import IncrementalEdges
from .compensated_sums import CompensatedSums
from .ordered_folds import OrderedFolds
from .group_scalars import GroupScalars
from .producer_fusion import ProducerFusion
from .fused_caches import FusedCaches
from .edge_algebra import EdgeAlgebra
from .losing_stores import LosingStores
from .width_dispatch import WidthDispatch
from .direct_routes import DirectRoutes
from .unroll_positions import UnrollPositions
from .base_edge_scalars import BaseEdgeScalars
from .base_prefix_scalars import BasePrefixScalars
from .base_integer_totals import BaseIntegerTotals
from .cancelled_products import CancelledProducts
from .retained_integer_edges import RetainedIntegerEdges
from .dead_primitive_slots import DeadPrimitiveSlots


IGNORED_DIRS = {".git", ".venv", ".cambc", "__pycache__", ".pytest_cache",
                ".ruff_cache", "build", "target"}
REPORT_NAME = "optimizer-report.json"


def source_hazards(tree):
    reasons = hazards(tree)
    imports = {alias.asname or alias.name.split(".")[0]
               for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in node.names}
    namespaces = {node.name for node in ast.walk(tree)
                  if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
    # Follow simple aliases as well: alias = Record; alias.field = descriptor
    # changes object.__setattr__ behaviour just as Record.field = descriptor does.
    while True:
        previous = len(namespaces)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in namespaces:
                namespaces.update(target.id for target in node.targets if isinstance(target, ast.Name))
        if len(namespaces) == previous:
            break
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del))
                and node.attr in {"__init__", "__new__", "__call__", "__getattribute__",
                                  "__getattr__", "__setattr__", "__class__", "__bases__",
                                  "__defaults__", "__kwdefaults__"}):
            reasons.append("mutation of callable/type implementation")
        if isinstance(node, ast.Global) and set(node.names) & (imports | {
            "len", "bool", "sum", "min", "max", "sorted", "range", "map", "abs",
        }):
            reasons.append("global mutation of a builtin/import binding")
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            root = node.value
            while isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            if isinstance(root, ast.Name) and root.id in imports:
                reasons.append("assignment through an imported object")
            if isinstance(root, ast.Name) and root.id in namespaces:
                reasons.append("assignment through a known callable/type namespace")
    return sorted(set(reasons))


def optimize_source(source: str, options: Options | None = None, *, filename="<bot>", blocked=(),
                    program=None, module_name="__bot__"):
    """Compile source without executing it. An unchanged module stays byte-for-byte."""
    options = options or Options()
    tree = ast.parse(source, filename=filename)
    compile(tree, filename, "exec")
    warnings = []
    if any(isinstance(node, ast.Attribute) and node.attr == "fuel_remaining"
           or isinstance(node, ast.ImportFrom) and any(a.name == "fuel_remaining" for a in node.names)
           for node in ast.walk(tree)):
        warnings.append("Fuel-dependent behaviour: lower fuel cost may change decisions or search limits.")
    reasons = sorted(set([*blocked, *source_hazards(tree)]))
    if reasons:
        warnings.append("Module left unchanged: " + "; ".join(reasons))
        return SourceResult(source, warnings=warnings)
    if program is None:
        program = Program({module_name: tree})
        regions = NumericRegions(program, options)
        regions.apply()
        program.region_changes = regions.changes
    # Use the indexed tree so class identity and source locations are unambiguous.
    tree = program.modules[module_name].tree
    record_returns = InlineRecordReturns(program, module_name, options)
    tree = ast.fix_missing_locations(record_returns.apply(tree))
    facts = HelperFacts()
    reductions = ShortReductions(program, module_name, options, facts)
    tree = ast.fix_missing_locations(reductions.apply(tree))
    shortcircuit = ShortCircuit(program, module_name, options, facts)
    tree = ast.fix_missing_locations(shortcircuit.apply(tree))
    extrema = ExtremumLoops(program, module_name, options, facts)
    tree = ast.fix_missing_locations(extrema.apply(tree))
    records = RecordSpecializer(program, module_name, options)
    tree = records.visit(tree)
    rewriter = Rewriter(options, program=program, module=module_name)
    tree = ast.fix_missing_locations(rewriter.visit(tree))
    extensions = AdjacentExtensions(program, module_name, options, facts)
    tree = ast.fix_missing_locations(extensions.apply(tree))
    scalar = ScalarExtrema(program, module_name, options)
    tree = ast.fix_missing_locations(scalar.apply(tree))
    adjacent = AdjacentPairs(program, module_name, options)
    tree = ast.fix_missing_locations(adjacent.apply(tree))
    insertions = TupleInsertions(program, module_name, options)
    tree = ast.fix_missing_locations(insertions.apply(tree))
    static_shapes = StaticHelperShapes(facts, options)
    tree = ast.fix_missing_locations(static_shapes.apply(tree))
    fact_reuse = ReuseHelperFacts(facts, options)
    tree = ast.fix_missing_locations(fact_reuse.apply(tree))
    numeric_ops = NumericOperations(options)
    tree = numeric_ops.apply(tree)
    tree = finish_numeric_regions(tree)
    entry_inlining = InlineNumericEntries(options)
    tree = entry_inlining.apply(tree)
    insertion_keys = InsertionKeys(options)
    tree = insertion_keys.apply(tree)
    incremental_edges = IncrementalEdges(options)
    tree = incremental_edges.apply(tree)
    compensated_sums = CompensatedSums(options)
    tree = compensated_sums.apply(tree)
    ordered_folds = OrderedFolds(options)
    tree = ordered_folds.apply(tree)
    group_scalars = GroupScalars(options)
    tree = group_scalars.apply(tree)
    producer_fusion = ProducerFusion(options)
    tree = producer_fusion.apply(tree)
    fused_caches = FusedCaches(options)
    tree = fused_caches.apply(tree)
    cancelled_products = CancelledProducts(options)
    tree = cancelled_products.apply(tree)
    edge_algebra = EdgeAlgebra(options)
    tree = edge_algebra.apply(tree)
    losing_stores = LosingStores(options)
    tree = losing_stores.apply(tree)
    width_dispatch = WidthDispatch(options)
    tree = width_dispatch.apply(tree)
    direct_routes = DirectRoutes(options)
    tree = direct_routes.apply(tree)
    unroll_positions = UnrollPositions(options)
    tree = unroll_positions.apply(tree)
    base_edge_scalars = BaseEdgeScalars(options)
    tree = base_edge_scalars.apply(tree)
    base_prefix_scalars = BasePrefixScalars(options)
    tree = base_prefix_scalars.apply(tree)
    base_integer_totals = BaseIntegerTotals(options)
    tree = base_integer_totals.apply(tree)
    retained_integer_edges = RetainedIntegerEdges(options)
    tree = retained_integer_edges.apply(tree)
    dead_primitive_slots = DeadPrimitiveSlots(options)
    tree = dead_primitive_slots.apply(tree)
    compile(tree, filename, "exec")
    changes = [*getattr(program, 'region_changes', {}).get(module_name, []),
                *record_returns.changes, *reductions.changes, *shortcircuit.changes,
                *extrema.changes, *records.changes, *rewriter.changes, *extensions.changes,
                *scalar.changes, *adjacent.changes, *insertions.changes,
                *static_shapes.changes, *fact_reuse.changes, *numeric_ops.changes, *entry_inlining.changes,
                *insertion_keys.changes, *incremental_edges.changes, *compensated_sums.changes, *ordered_folds.changes,
                *group_scalars.changes, *producer_fusion.changes, *fused_caches.changes, *edge_algebra.changes,
                *losing_stores.changes, *width_dispatch.changes, *direct_routes.changes, *unroll_positions.changes,
                *base_edge_scalars.changes, *base_prefix_scalars.changes, *base_integer_totals.changes,
                *cancelled_products.changes, *retained_integer_edges.changes, *dead_primitive_slots.changes]
    if not changes:
        return SourceResult(source, warnings=warnings)
    emitted = ast.unparse(tree) + "\n"
    # This second parse catches errors in emission, not just AST construction.
    compile(emitted, filename, "exec")
    return SourceResult(emitted, changes, warnings)


def inventory(folder, root=None):
    """Reject symlinks rather than reading/copying outside the supplied folder."""
    root = root or folder
    for entry in sorted(folder.iterdir()):
        if entry.is_symlink():
            raise ValueError(f"Symlinks are not supported: {entry}")
        if entry.is_dir():
            excluded = entry.name in IGNORED_DIRS and (
                entry.name not in {"build", "target"} or folder == root
            )
            if not excluded:
                yield from inventory(entry, root)
        elif entry.is_file() and entry.suffix not in {".pyc", ".pyo"}:
            yield entry


def optimize_folder(source, output, options: Options | None = None):
    options = options or Options()
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_dir():
        raise ValueError(f"Bot folder does not exist: {source}")
    if output == source or source in output.parents or output in source.parents:
        raise ValueError("Input and output must be separate, non-overlapping folders")
    if output.exists():
        raise ValueError(f"Output already exists (nothing overwritten): {output}")
    src = source / "src" if (source / "src" / "main.py").is_file() else source
    if not (src / "main.py").is_file():
        raise ValueError("Expected src/main.py (or main.py) in the input bot")
    files = list(inventory(source))
    python = [p for p in files if p.suffix == ".py" and (src == p.parent or src in p.parents)]
    texts = {}
    for path in python:
        with tokenize.open(path) as stream:
            texts[path] = stream.read()
    # Dynamic imports/reflection or module patching anywhere in the submitted
    # source can invalidate another module's bindings. Bail out folder-wide.
    blocked = sorted({reason for path, text in texts.items()
                       for reason in source_hazards(ast.parse(text, filename=str(path)))})
    modules, packages = {}, set()
    for path in texts:
        parts = list(path.relative_to(src).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
            packages.add(".".join(parts))
        modules[path] = ".".join(parts) or "__root__"
    if len(set(modules.values())) != len(modules):
        raise ValueError("Ambiguous Python module/package names in the input folder")
    program = Program({modules[path]: ast.parse(text, filename=str(path.relative_to(source)))
                        for path, text in texts.items()}, packages)
    if not blocked:
        regions = NumericRegions(program, options)
        regions.apply()
        program.region_changes = regions.changes
    results = {path: optimize_source(text, options, filename=str(path.relative_to(source)), blocked=blocked,
                                     program=program, module_name=modules[path])
               for path, text in texts.items()}
    counts = Counter(change.pass_name for result in results.values() for change in result.changes)
    fingerprint = hashlib.sha256()
    for path in files:
        fingerprint.update(str(path.relative_to(source)).encode())
        fingerprint.update(b"\0")
        fingerprint.update(path.read_bytes())
        fingerprint.update(b"\0")
    report = {
        "schema_version": 1,
        "optimizer_version": "0.2.0",
        "input_sha256": fingerprint.hexdigest(),
        "target": {"cambc": options.target, "guest_python": "3.13.7"},
        "options": options.to_dict(),
        "assumptions": [
            "Public cambc 3.0.4 SDK contracts and standard Python builtins are not monkey-patched.",
            "No external reflection, tracing, or mutation of function/module namespaces.",
            "Resolved bot functions and record types are not monkey-patched, including via external aliases.",
            "Fuel counters, allocation identity, traceback text and implicit suspension timing may differ.",
            *(["Supported parameter annotations describe exact runtime types (explicit opt-in)."]
              if options.trust_annotations else []),
        ],
        "validation": {"syntax": "passed", "behavioural_equivalence": "not established by syntax checks",
                       "fuel": "not measured; use the paired benchmark runner"},
        "pass_counts": dict(sorted(counts.items())),
        "analysis": program.diagnostics(),
        "files": {str(path.relative_to(source)): result.diagnostics() for path, result in results.items()},
        "copied_files": len(files),
        "excluded_directories": sorted(IGNORED_DIRS),
    }
    # All parsing/analysis succeeds before creating the output directory.
    output.mkdir(parents=True)
    for path in files:
        relative = path.relative_to(source)
        if relative == Path(REPORT_NAME):
            continue  # A previous optimiser report is not a bot asset.
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if path in results and results[path].changes:
            destination.write_text(results[path].source, encoding="utf-8")
            shutil.copymode(path, destination)
        else:
            shutil.copy2(path, destination)
    (output / REPORT_NAME).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
