"""Research-only avoid materializing dictionaries on private losing records.

Record allocation count/order remain unchanged. This candidate extends the
store-omission experiment and needs a separate managed-dictionary/GC/lifetime
proof; the production pass intentionally still materializes every dictionary.
"""

import argparse
import ast
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tools.bot_optimizer.compare as measurement


def transform(folder):
    path=folder/'src/planner.py'
    tree=ast.parse(path.read_text())
    consumer,=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name.startswith('_bcopt_region_consumer_')]
    changes=0
    for parent in ast.walk(consumer):
        for _,body in ast.iter_fields(parent):
            if not isinstance(body,list):
                continue
            guards=[n for n in body if isinstance(n,ast.If) and isinstance(n.test,ast.Name)
                    and n.test.id.startswith('_bcopt_losing_keep')]
            for guard in guards:
                stores=guard.body
                assert stores and all(isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Subscript) for n in stores)
                dictionary=stores[0].targets[0].value.id
                assert all(n.targets[0].value.id==dictionary for n in stores)
                materialize,=[n for n in body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
                              and n.targets[0].id==dictionary]
                release,=[n for n in body if isinstance(n,ast.Delete) and len(n.targets)==1
                           and isinstance(n.targets[0],ast.Name) and n.targets[0].id==dictionary]
                assert isinstance(materialize.value,ast.Attribute) and materialize.value.attr=='__dict__'
                assert body.index(materialize)<body.index(guard)<body.index(release)
                body.remove(materialize)
                body.remove(release)
                guard.body=[materialize,*stores,release]
                changes+=1
    assert changes==78,changes
    source=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    compile(source,str(path),'exec')
    path.write_text(source)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--maps',default='collision')
    args=parser.parse_args()
    original=measurement.optimize_folder
    def compile_variant(bot,output,options):
        report=original(bot,output,options)
        if not options.disabled:
            transform(output)
            report['pass_counts']['experiment-losing-dicts']=1
        return report
    measurement.optimize_folder=compile_variant
    report=measurement.compare(args.bot,args.output,target='draft_planner:DraftPlanner.build',
                               maps=tuple(args.maps.split(',')),repeats=1,output_prefix='SQUAD_LOOPS_DATA ')
    report['experimental_post_compile_transform']='losing-record dictionary materialization omission, research only'
    (args.output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    for row in report['comparisons']:
        print(row['map'],row['side'],row['reduction_percent'])


if __name__=='__main__':
    main()
