"""Manual planner region feasibility probe; not an accepted generic compiler pass.

Fresh generated copy only. Primitive snapshots are renewed each search level.
The private clone is reached only from the known SDK budget-callback callsite;
public methods and all unknown-callback paths retain the current compiler output.
"""

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.bot_optimizer import optimize_folder
from tools.bot_optimizer.compare import instrument, observations
from tools.bot_optimizer.runtime import executable, run_command


HELPERS = '''
from types import MethodType as _region_method_type
_region_original_evaluate=LoopPlanner.evaluate_loop
_region_original_find=LoopPlanner.find_loops
_region_original_risk=LoopPlanner._calculate_loop_risk
_region_original_insertions=camp_insertions

def _region_context(self,camps,config,beams,evaluate):
    if type(self) is not LoopPlanner or camp_insertions is not _region_original_insertions:
        return None
    if type(evaluate) is not _region_method_type or evaluate.__func__ is not _region_original_evaluate or evaluate.__self__ is not self:
        return None
    risk_method=self._calculate_loop_risk
    if type(risk_method) is not _region_method_type or risk_method.__func__ is not _region_original_risk or risk_method.__self__ is not self:
        return None
    try:
        if self.camps is not camps or self.config is not config or type(config) is not SearchConfig:
            return None
        matrix,altars,spawn,risk=self.distances,self.altar_distances,self.spawn_distances,self.risk
        gold_weight,opening_weight,tolerance=config.gold_weight,config.opening_weight,config.risk_tolerance
        limits=config.max_camps,config.max_expansions,config.beam_width
    except AttributeError:
        return None
    if not (type(camps) is list or type(camps) is tuple):
        return None
    if not all(type(value) is int for value in limits):
        return None
    if not all(type(value) is int or type(value) is float for value in (gold_weight,opening_weight,tolerance)):
        return None
    n=len(camps)
    packed=[]
    services=[]
    for row in camps:
        if type(row) is not CampGroupInfo:
            return None
        try:
            a,b,s,r=row.gems,row.gold,row.service_turns,row.respawn_turns
        except AttributeError:
            return None
        if not (type(a) is int and type(b) is int and type(s) is int and type(r) is int):
            return None
        packed.append((a,b,s,r))
        services.append(s)
    if not (type(matrix) is list or type(matrix) is tuple) or len(matrix)!=n:
        return None
    if not (type(altars) is list or type(altars) is tuple):
        return None
    copied=[]
    for table in (matrix,altars):
        rows=[]
        for row in table:
            if not (type(row) is list or type(row) is tuple) or len(row)!=n:
                return None
            for value in row:
                if type(value) is not int:
                    return None
            rows.append(tuple(row))
        copied.append(tuple(rows))
    if not (type(spawn) is list or type(spawn) is tuple) or len(spawn)!=n:
        return None
    for value in spawn:
        if type(value) is not int:
            return None
    weights=altar_risks=None
    if risk is not None:
        if type(risk) is not RiskProfile:
            return None
        try:
            weights,altar_risks=risk.camps,risk.altars
        except AttributeError:
            return None
        if type(weights) is not tuple or type(altar_risks) is not tuple or len(weights)!=n or len(altar_risks)!=len(altars):
            return None
        for value in (*weights,*altar_risks):
            if type(value) is not float:
                return None
    if type(beams) is not dict:
        return None
    for altar,beam in beams.items():
        if type(altar) is not int or not 0<=altar<len(altars) or not (type(beam) is list or type(beam) is tuple):
            return None
        for route in beam:
            if type(route) is not tuple:
                return None
            for index in route:
                if type(index) is not int or not 0<=index<n:
                    return None
    return (tuple(packed),tuple(services),*copied,tuple(spawn),weights,altar_risks,
            gold_weight,opening_weight,tolerance)

def _region_evaluate(data,route,altar_index):
    if not route:
        return None
    packed,services,matrix,altars,spawn,weights,altar_risks,gold_weight,opening_weight,tolerance=data
    first_camp,last_camp=route[0],route[-1]
    legs=[altars[altar_index][first_camp],altars[altar_index][last_camp]]
    legs.extend([matrix[a][b] for a,b in zip(route,route[1:])])
    for distance in legs:
        if distance<0:
            return None
    if spawn[first_camp]<0:
        return None
    gems=gold=service_turns=0
    respawn_floor=None
    for index in route:
        a,b,s,r=packed[index]
        gems+=a
        gold+=b
        service_turns+=s
        value=r+s
        if respawn_floor is None or value>respawn_floor:
            respawn_floor=value
    tribute_turns=ceil(gems/10)
    travel_turns=sum(legs)
    active_turns=travel_turns+service_turns+tribute_turns
    period=respawn_floor if respawn_floor>active_turns else active_turns
    first_deposit=active_turns-legs[0]+spawn[first_camp]
    reward_value=gems+gold_weight*gold
    base_score=reward_value/(period+opening_weight*first_deposit)
    loop_risk=0.0
    if weights is not None:
        altar_risk=altar_risks[altar_index]
        exposure=legs[0]*(altar_risk+weights[first_camp])/2
        exposure+=legs[1]*(weights[last_camp]+altar_risk)/2
        for origin,destination,distance in zip(route,route[1:],legs[2:]):
            combined_risk=weights[origin]+weights[destination]
            exposure+=distance*combined_risk/2
        exposure+=sum([services[index]*weights[index] for index in route])
        exposure+=(tribute_turns+period-active_turns)*altar_risk
        value=exposure/period
        inner=value if value>0.0 else 0.0
        loop_risk=inner if inner<1.0 else 1.0
    risk_multiplier=1-(1-tolerance)*loop_risk
    # The existing compiler's record-return sequence is spliced here verbatim.
'''


def transform(folder):
    path = folder / 'src/planner.py'
    tree = ast.parse(path.read_text())
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'LoopPlanner')
    methods = {n.name: n for n in owner.body if isinstance(n, ast.FunctionDef)}
    helpers = ast.parse(HELPERS).body
    fast = next(n for n in helpers if isinstance(n, ast.FunctionDef) and n.name == '_region_evaluate')
    evaluation = methods['evaluate_loop']
    tail = None
    for branch in ast.walk(evaluation):
        if not isinstance(branch, ast.If):
            continue
        for body in (branch.body, branch.orelse):
            for index, statement in enumerate(body):
                if (isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name)
                        and statement.targets[0].id == '_bcopt_return_value_0'):
                    tail = copy.deepcopy(body[index:])
    if tail is None:
        raise ValueError('Expected the current record-return lowering')
    fast.body.extend(tail)
    clone = copy.deepcopy(methods['find_loops'])
    clone.name = '_region_find_loops'
    clone.args.kwonlyargs.append(ast.arg(arg='_callback_safe'))
    clone.args.kw_defaults.append(ast.Constant(False))
    outer = next(n for n in clone.body if isinstance(n, ast.For))
    outer.body[:0] = ast.parse('_region_data = _region_context(self,camps,config,beams,evaluate) if _callback_safe else None').body

    class Dispatch(ast.NodeTransformer):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == 'evaluate':
                assert ast.unparse(node) == 'evaluate(route, altar_index)'
                return ast.IfExp(test=ast.parse('_region_data is not None', mode='eval').body,
                    body=ast.parse('_region_evaluate(_region_data,route,altar_index)', mode='eval').body,
                    orelse=node)
            return self.generic_visit(node)

    clone = Dispatch().visit(clone)
    tree.body.extend([*helpers, clone])
    path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    compile(path.read_text(), str(path), 'exec')

    path = folder / 'src/draft_planner.py'
    tree = ast.parse(path.read_text())
    index = next(i for i,n in enumerate(tree.body) if isinstance(n,ast.FunctionDef) and n.name=='draft_budget_exhausted')
    tree.body[index+1:index+1] = ast.parse('''_region_original_stop=draft_budget_exhausted
from planner import _region_find_loops, _region_original_find, _region_method_type
''').body
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DraftPlanner')
    search = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_search')
    original = search.body[-1]
    assert isinstance(original, ast.Return) and isinstance(original.value, ast.Call)
    # This manual probe has a known callsite. A generic pass must derive its
    # callback/constructor/loop-region eligibility rather than use these names.
    branch = ast.parse('''if (draft_budget_exhausted is _region_original_stop and type(settings.FUEL_RESERVE) is int
        and type(planner) is LoopPlanner and type(planner.find_loops) is _region_method_type
        and planner.find_loops.__func__ is _region_original_find):
    return _region_find_loops(planner,should_stop=draft_budget_exhausted,limit=settings.REPORT_LIMIT,_callback_safe=True)
''').body[0]
    search.body[-1:] = [branch, original]
    path.write_text(ast.unparse(ast.fix_missing_locations(tree))+'\n')
    compile(path.read_text(), str(path), 'exec')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maps', default='collision,corners,lanes')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be fresh')
    folder = args.output.resolve() / 'candidate'
    report = optimize_folder(args.bot, folder)
    transform(folder)
    result = {'status':'prepared','manual_candidate':True,'input_sha256':report['input_sha256'],
              'source_sha256':{str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted((folder/'src').glob('*.py'))},'runs':[]}
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    if args.prepare_only:
        return
    instrument(folder,'draft_planner:DraftPlanner.build')
    for repeat in range(args.repeats):
        for game_map in args.maps.split(','):
            destination = args.output.resolve()/f'run-{repeat}-{game_map}'
            run_command([executable(),'run',str(folder),str(folder),'--release','--rounds','1',
                         '--fuel','1000000000','--map',game_map,'--out-dir',str(destination)],timeout=300)
            replay, = destination.glob('*.repl26a')
            observed = observations(replay,'SQUAD_LOOPS_DATA ')
            result['runs'].append({'repeat':repeat,'map':game_map,'observations':observed})
            for side,data in observed.items():
                print(game_map,side,sum(data['samples']),flush=True)
            (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    result['status']='complete'
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__ == '__main__':
    main()
