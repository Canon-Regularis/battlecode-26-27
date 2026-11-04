"""Preserved, paired configuration generations for leader_party_subhan.

Commands: init; build NAME...; run LABEL --candidates NAME... --opponents NAME...
          --split screen|train|validation|holdout|broad; rank LABEL
Each completed replay is reusable on resume. No random seed repetitions are counted.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'docs/strategy/leader_party/evaluation/2026-11-04/tuning'
LOCAL=ROOT/'.cambc/tuning'
CLI=ROOT/'.venv/Scripts/cambc.exe'
DEFAULTS=dict(bank_bag=20,bag_age=40,stall=8,task_limit=90,max_clear=90,
              protection_limit=12,retry=10,wards=True,value_routing=False,
              recovery_low=.35,recovery_high=.55,recall_gold=300,competition_cost=4,
              loop_candidates=24,loop_altars=4,loop_beam=4,loop_length=5,
              loop_expansions=768,loop_reports=3,loop_gold=.02,loop_opening=.15,
              loop_risk=.2,loop_service=7,loop_phase=2,
              rally_life=12,lease=3,reserve=10000,field_admission=55000,
              max_fields=3,coordination=False,attacks=False)

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    temporary.replace(path)

def read(path):return json.loads(path.read_text())

def replace(text,old,new):
    assert old in text,old
    return text.replace(old,new)

def create(name,changes,parent='g00'):
    registry=read(STORE/'generations.json') if (STORE/'generations.json').exists() else {}
    assert name not in registry,name
    assert parent in registry or parent=='leader_party_subhan','Unknown parent generation'
    assert not set(changes)-set(DEFAULTS),'Unknown configuration setting'
    config={**DEFAULTS,**(registry[parent]['config'] if parent in registry else {}),**changes}
    assert set(config)==set(DEFAULTS)
    assert 0<=config['recovery_low']<config['recovery_high']<=1
    assert 1<=config['loop_length']<=5 and 1<=config['loop_reports']<=3
    assert 1<=config['loop_candidates']<=48 and 1<=config['loop_altars']<=255
    assert 1<=config['loop_beam']<=32 and 1<=config['loop_expansions']<=20000
    assert 0<=config['reserve']<config['field_admission']<=200000
    assert all(config[k]>0 for k in ['bank_bag','bag_age','stall','task_limit','max_clear','max_fields'])
    assert all(config[k]>=0 for k in ['protection_limit','retry','rally_life','lease'])
    assert 0<=config['loop_phase']<=10 and config['loop_service']>=0
    assert all(config[k]>=0 for k in ['recall_gold','competition_cost','loop_gold','loop_opening','loop_risk'])
    target=ROOT/'bots'/('lp_tune_'+name)
    assert not target.exists(),target
    shutil.copytree(ROOT/'bots/leader_party_subhan',target,
                    ignore=shutil.ignore_patterns('.cambc','build','__pycache__'))
    header=(target/'src/config.h').read_text()
    import re
    for key,value in config.items():
        literal=str(value).lower()
        if key in ['bank_bag','bag_age','stall','task_limit','max_clear','protection_limit','retry','wards','value_routing','rally_life','lease','reserve','field_admission','max_fields','coordination','attacks']:
            header,n=re.subn(r'\b'+key+r'=\w+',key+'='+literal,header)
            assert n==1,key
        else:
            kind='float' if key.startswith('recovery_') else 'double' if key in ['loop_gold','loop_opening','loop_risk'] else 'int'
            if kind=='float':literal=str(float(value))+'f'
            header=header.replace('struct Config {','struct Config {\n    static constexpr '+kind+' '+key+'='+literal+';')
    (target/'src/config.h').write_text(header,encoding='utf-8',newline='\n')
    changesets={
        'model.h': [('bag>=20','bag>=Config::bank_bag'),('round-since>=40','round-since>=Config::bag_age')],
        'bot.cpp': [('0.35f','Config::recovery_low'),('0.55f','Config::recovery_high'),('gold_count()>=300','gold_count()>=Config::recall_gold'),('memory.shop_phase<2','memory.shop_phase<Config::loop_phase')],
        'combat.cpp': [('0.55f','Config::recovery_high')],
        'objectives.cpp': [('competitors*4','competitors*Config::competition_cost')],
        'route_plan.cpp': [('all.size()>24','all.size()>Config::loop_candidates'),('all.begin()+24','all.begin()+Config::loop_candidates'),('altars.size()>4','altars.size()>Config::loop_altars'),('altars.resize(4)','altars.resize(Config::loop_altars)'),
            ('cfg.beam_width=4;cfg.max_camps=5;cfg.max_expansions=768;cfg.report_limit=3;',
             'cfg.beam_width=Config::loop_beam;cfg.max_camps=Config::loop_length;cfg.max_expansions=Config::loop_expansions;cfg.report_limit=Config::loop_reports;cfg.gold_weight=Config::loop_gold;cfg.opening_weight=Config::loop_opening;cfg.risk_tolerance=Config::loop_risk;'),
            ('std::ceil(c.hp/damage))+7','std::ceil(c.hp/damage))+Config::loop_service')],
        'tests/decisions.cpp': [('bank_due(4,10,50,0)&&!bank_due(4,10,49,0)','bank_due(1,10,10+Config::bag_age,0)&&!bank_due(1,10,9+Config::bag_age,0)'),('task_expired(20,0,12)&&!task_expired(20,0,13)','task_expired(Config::stall,0,0)&&!task_expired(Config::stall-1,0,0)'),('wire::live(first,21,6,49)&&!wire::live(first,22,6,49)','(Config::rally_life==0?!wire::live(first,10,6,49):wire::live(first,10+Config::rally_life-1,6,49))&&!wire::live(first,10+Config::rally_life,6,49)'),('wire::live(late,2000,6,49)','(wire::live(late,2000,6,49)==(Config::rally_life>1))'),('wire::leader_live(leader,103,6)&&!wire::leader_live(leader,104,6)','wire::leader_live(leader,100+Config::lease,6)&&!wire::leader_live(leader,101+Config::lease,6)')]
    }
    for filename,pairs in changesets.items():
        path=target/filename if filename.startswith('tests/') else target/'src'/filename
        content=path.read_text()
        for old,new in pairs:content=replace(content,old,new)
        if filename=='tests/decisions.cpp':
            content=replace(content,'    check(bank_due(2,10,20,998)',
                '    check(bank_due(Config::bank_bag,-1,0,0)&&!bank_due(Config::bank_bag-1,-1,0,0),"configured bag threshold");\n    check(bank_due(2,10,20,998)')
        path.write_text(content,encoding='utf-8',newline='\n')
    (target/'README.md').write_text(f'# Configuration generation {name}\n\nParent: `{parent}`. Generated from the preserved `leader_party_subhan` source.\n\nSee [tuning evidence](../../docs/strategy/leader_party/evaluation/2026-11-04/tuning/generations.json) for the complete configuration and artifact hashes.\n',encoding='utf-8',newline='\n')
    source={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (target/'src').glob('*') if p.is_file()}
    registry[name]=dict(parent=parent,bot=target.name,config=config,changes_from_parent=changes,source_sha256=source)
    save(STORE/'generations.json',registry)

def init():
    assert not (STORE/'experiment.json').exists(),'Experiment already initialized'
    rng=random.Random(2026110417)
    splits=dict(screen=[],train=[],validation=[],holdout=[])
    for prefix in ['00','01','02','03','adgato']:
        maps=sorted(p.stem for p in (ROOT/'maps').glob(prefix+'*.map26a'))
        rng.shuffle(maps)
        n=4 if prefix!='adgato' else 1
        v=4 if prefix!='adgato' else 2
        splits['train']+=maps[:n];splits['validation']+=maps[n:n+v];splits['holdout']+=maps[n+v:]
        splits['screen']+=maps[:2] if prefix!='adgato' else []
    save(STORE/'experiment.json',dict(seed=2026110417,splits=splits,
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        policy='Screen on eight maps; expand winners on training maps; freeze finalist before validation and holdout. Paired sides; equal opponent weight; wins primary, score margin secondary; no VM faults permitted. No duplicate deterministic conditions counted.'))
    create('g00',{},'leader_party_subhan')
    candidates={
        'g01_bank12':dict(bank_bag=12,bag_age=25),
        'g01_bank30':dict(bank_bag=30,bag_age=60),
        'g01_bank40':dict(bank_bag=40,bag_age=80),
        'g01_recover_early':dict(recovery_low=.45,recovery_high=.65),
        'g01_recover_late':dict(recovery_low=.25,recovery_high=.45),
        'g01_clear60':dict(max_clear=60,task_limit=70),
        'g01_clear120':dict(max_clear=120,task_limit=120),
        'g01_risk_safe':dict(loop_risk=0.,loop_opening=.3),
        'g01_risk_bold':dict(loop_risk=.5,loop_opening=.05),
        'g01_search_wide':dict(loop_beam=8,loop_expansions=1536),
        'g01_loop_short':dict(loop_length=3,loop_service=12),
        'g01_no_wards':dict(wards=False),
    }
    for name,changes in candidates.items():create(name,changes)
    print(json.dumps(splits));print('Created g00 and',len(candidates),'first-generation clones',flush=True)

def build(names,jobs=1):
    registry=read(STORE/'generations.json');LOCAL.mkdir(parents=True,exist_ok=True)
    def compile_one(name):
        entry=registry[name];bot=entry['bot']
        assert all(hashlib.sha256((ROOT/'bots'/bot/p).read_bytes()).hexdigest()==h for p,h in entry['source_sha256'].items()),'Generation source changed after recording'
        with (LOCAL/(name+'-build.log')).open('w') as log:
            subprocess.run([str(CLI),'build',bot,'--release'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        data=(ROOT/'bots'/bot/'.cambc/build-release/bot-injected.wasm').read_bytes()
        artifact=LOCAL/(name+'.zip')
        with zipfile.ZipFile(artifact,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('bot.wasm',data);z.writestr('manifest.json',json.dumps(dict(apiVersion=1,status='ready',language='cpp')))
        return name,hashlib.sha256(data).hexdigest(),str(artifact.relative_to(ROOT))
    assert len(names)==len(set(names)),'Duplicate build target'
    # Only the caller writes the shared registry; workers own separate bot trees.
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        for name,digest,artifact_path in executor.map(compile_one,names):
            registry[name]['wasm_sha256']=digest
            registry[name]['artifact']=artifact_path
            save(STORE/'generations.json',registry)
            print('BUILT',name,digest,flush=True)

def artifact(name):
    fixed={'subhan':'.cambc/leader-party-subhan-v1.zip','original':'.cambc/leader-party-validated.zip',
           'D1':'.cambc/D1-compiled.zip','gold_diamond':'.cambc/gold_diamond-compiled.zip','larpbot':'.cambc/larpbot-compiled.zip'}
    if name.startswith('pool'):
        index=int(name[4:]);inventory=read(ROOT/'docs/strategy/leader_party/evaluation/2026-11-04/all-bots-results.json')['inventory']
        path=ROOT/'.cambc'/f'all-bots-20261104-{index}.zip'
        with zipfile.ZipFile(path) as z:assert hashlib.sha256(z.read('bot.wasm')).hexdigest()==inventory[index]['sha256']
        return path
    if name in fixed:return ROOT/fixed[name]
    entry=read(STORE/'generations.json')[name]
    path=ROOT/entry['artifact']
    assert all(hashlib.sha256((ROOT/'bots'/entry['bot']/p).read_bytes()).hexdigest()==h for p,h in entry['source_sha256'].items()),'Generation source changed'
    with zipfile.ZipFile(path) as z:assert hashlib.sha256(z.read('bot.wasm')).hexdigest()==entry['wasm_sha256']
    return path

def run(args):
    LOCAL.mkdir(parents=True,exist_ok=True)
    if args.split=='broad':assert args.maps,'Broad checks require an explicit map list'
    maps=args.maps or read(STORE/'experiment.json')['splits'][args.split]
    names=set(args.candidates+args.opponents)
    def team(name):
        path=artifact(name)
        with zipfile.ZipFile(path) as z:language=json.loads(z.read('manifest.json'))['language']
        return dict(name=name,path=str(path),language=language)
    teams={n:team(n) for n in names}
    out=ROOT/'replays/leader-party/tuning/cache';out.mkdir(parents=True,exist_ok=True)
    hashes={n:hashlib.sha256(artifact(n).read_bytes()).hexdigest() for n in sorted(names)}
    jobs=[];meta=[]
    for c in args.candidates:
        for o in args.opponents:
            if c==o:continue
            for m in maps:
                for swap in range(2):
                    ident=f'{len(jobs):05d}';a,b=(o,c) if swap else (c,o)
                    key=hashlib.sha256(json.dumps([a,hashes[a],b,hashes[b],m,hashlib.sha256((ROOT/'maps'/(m+'.map26a')).read_bytes()).hexdigest(),'CAMBC 4.0.0 release default']).encode()).hexdigest()[:24]
                    jobs.append(dict(apiVersion=1,id=ident,teamA=teams[a],teamB=teams[b],map=str(ROOT/'maps'/(m+'.map26a')),replay=str(out/(key+'.zip'))))
                    meta.append(dict(candidate=c,opponent=o,map=m,side='teamB' if swap else 'teamA'))
    receipt=STORE/(args.label+'.json')
    design=dict(label=args.label,split=args.split,maps=maps,candidates=args.candidates,opponents=args.opponents,
                artifact_sha256=hashes,planned_games=len(jobs))
    if receipt.exists():
        old=read(receipt)
        assert all(old[k]==v for k,v in design.items()),'Cannot change a running/frozen experiment'
        if old['status']=='complete':print('Already complete:',receipt);return
    save(receipt,dict(**design,status='running'))
    pending=[];interrupted=[]
    for j in jobs:
        path=Path(j['replay'])
        if path.exists():
            try:
                with zipfile.ZipFile(path) as z:z.read('summary.camstat')
            except (zipfile.BadZipFile,KeyError,EOFError):
                assert path.resolve().is_relative_to(out.resolve())
                preserved=path.with_suffix('.interrupted.zip')
                assert not preserved.exists(),preserved
                path.replace(preserved);interrupted.append(str(preserved.relative_to(ROOT)))
        if not path.exists() and not any(existing['replay']==j['replay'] for existing in pending):pending.append(j)
    if interrupted:save(LOCAL/(args.label+'-interrupted.json'),interrupted)
    print(args.label,'conditions',len(jobs),'cached',len(jobs)-len(pending),'new',len(pending),flush=True)
    for batch,start in enumerate(range(0,len(pending),120)):
        manifest=LOCAL/f'{args.label}-{batch}.jsonl'
        manifest.write_text(''.join(json.dumps(j)+'\n' for j in pending[start:start+120]))
        with (LOCAL/f'{args.label}-{batch}-events.jsonl').open('w') as log:
            subprocess.run([str(CLI),'run-batch','--jsonl',str(manifest),'--jobs',str(args.jobs),'--release','--log-limit','200000'],cwd=ROOT,stdout=log,check=True)
        print(args.label,'batch',batch+1,'/',(len(pending)+119)//120,'done',flush=True)
    def summarize(pair):
        j,info=pair
        stem=Path(j['replay']).stem
        cache=LOCAL/'summaries'/(stem+'-'+info['candidate']+'-'+info['side']+'.json')
        legacy=LOCAL/'summaries'/(stem+'.json')
        if not cache.exists() and legacy.exists():
            row=read(legacy)
            if all(row[k]==v for k,v in info.items()):return row
        if cache.exists():
            row=read(cache)
            assert all(row[k]==v for k,v in info.items()),'Cached summary metadata mismatch'
            return row
        with zipfile.ZipFile(j['replay']) as z:
            raw=LOCAL/(cache.stem+'-summary.camstat');raw.write_bytes(z.read('summary.camstat'))
            d=json.loads(subprocess.check_output([str(CLI),'summary',str(raw),'-o','-']))
            logs={s:z.read(f'team-{a}.stdout').replace(b'\0',b'').decode(errors='replace') for s,a in [('teamA','a'),('teamB','b')]}
        ours=info['side'];other='teamA' if ours=='teamB' else 'teamB'
        scores={t['team']:int(t['submittedGems']) for t in d['teams']}
        outcome=d['match']['outcome']
        def metric(side,key):return sum(float(c['metrics'][key]) for c in d['champions'] if c['team']==side)
        row=dict(**info,result='win' if outcome==ours else 'loss' if outcome==other else 'draw',
            ours=scores[ours],theirs=scores[other],zero_score=scores[ours]==scores[other]==0,
            seed=d['match']['seed'],rounds=d['match']['roundsStarted'],faults=d['diagnostics']['botFaults'],
            errors=logs[ours].count('LP_ERROR'),opponent_errors=logs[other].count('LP_ERROR'),
            deaths=metric(ours,'deaths'),opponent_deaths=metric(other,'deaths'),
            draft=[l for l in logs[ours].splitlines() if l.startswith('SUBHAN_DRAFT')],
            replay=str(Path(j['replay']).relative_to(ROOT)))
        save(cache,row)
        return row
    with ThreadPoolExecutor(max_workers=4) as executor:
        rows=list(executor.map(summarize,zip(jobs,meta)))
    save(receipt,dict(**design,status='complete',matches=rows))
    rank(args.label)

def rank(label):
    d=read(STORE/(label+'.json'));groups=defaultdict(list)
    for r in d['matches']:groups[r['candidate']].append(r)
    summaries=[]
    for name,rs in groups.items():
        opponents={o:[r for r in rs if r['opponent']==o] for o in sorted({r['opponent'] for r in rs})}
        rates=[sum(r['result']=='win' for r in rows)/len(rows) for rows in opponents.values()]
        summaries.append(dict(name=name,games=len(rs),wins=sum(r['result']=='win' for r in rs),
            opponent_mean_win_rate=sum(rates)/len(rates),margin=sum(r['ours']-r['theirs'] for r in rs)/len(rs),
            faults=sum(r['faults'][r['side']] for r in rs),errors=sum(r['errors'] for r in rs),
            zero_score=sum(r['zero_score'] for r in rs),versus={o:dict(wins=sum(r['result']=='win' for r in rows),games=len(rows)) for o,rows in opponents.items()}))
    summaries.sort(key=lambda r:(-r['faults'],r['opponent_mean_win_rate'],r['margin']),reverse=True)
    save(STORE/(label+'-ranking.json'),summaries)
    for s in summaries:print(json.dumps(s),flush=True)

def compare(labels,baseline):
    unique={}
    for label in labels:
        data=read(STORE/(label+'.json'));assert data['status']=='complete'
        for row in data['matches']:
            key=(row['candidate'],row['opponent'],row['map'],row['side'])
            if key in unique:assert unique[key]==row,'Deterministic condition changed'
            unique[key]=row
    base={(o,m,s):r for (c,o,m,s),r in unique.items() if c==baseline}
    report=[]
    for candidate in sorted({k[0] for k in unique}-{baseline}):
        pairs=[(r,base[o,m,s]) for (c,o,m,s),r in unique.items() if c==candidate and (o,m,s) in base]
        if not pairs:continue
        grouped=defaultdict(list)
        for row,control in pairs:grouped[row['map']].append((row,control))
        win_delta=[statistics.mean((r['result']=='win')-(b['result']=='win') for r,b in rows) for rows in grouped.values()]
        margin_delta=[statistics.mean((r['ours']-r['theirs'])-(b['ours']-b['theirs']) for r,b in rows) for rows in grouped.values()]
        rng=random.Random(127)
        boot=sorted(statistics.mean(rng.choices(win_delta,k=len(win_delta))) for _ in range(10000))
        item=dict(candidate=candidate,baseline=baseline,matched_conditions=len(pairs),maps=len(grouped),
            wins=sum(r['result']=='win' for r,b in pairs),baseline_wins=sum(b['result']=='win' for r,b in pairs),
            win_delta=statistics.mean(win_delta),map_cluster_win_delta_95=[boot[249],boot[9749]],
            margin_delta=statistics.mean(margin_delta),errors=sum(r['errors'] for r,b in pairs),baseline_errors=sum(b['errors'] for r,b in pairs),
            faults=sum(r['faults'][r['side']] for r,b in pairs))
        report.append(item);print(json.dumps(item),flush=True)
    save(STORE/('comparison-'+labels[-1]+'.json'),dict(labels=labels,baseline=baseline,results=report))

def leaderboard(split):
    maps=read(STORE/'experiment.json')['splits'][split]
    opponents=['subhan','D1','gold_diamond','original','larpbot']
    conditions={}
    for path in STORE.glob('*.json'):
        data=read(path)
        if not isinstance(data,dict) or data.get('status')!='complete':continue
        for row in data.get('matches',[]):
            if row['map'] not in maps or row['opponent'] not in opponents:continue
            key=(row['candidate'],row['opponent'],row['map'],row['side'])
            if key in conditions:assert conditions[key]==row
            conditions[key]=row
    groups=defaultdict(list)
    for (candidate,*_),row in conditions.items():groups[candidate].append(row)
    rows=[]
    for candidate,matches in groups.items():
        if len(matches)!=len(maps)*2*len(opponents):continue
        rows.append(dict(candidate=candidate,games=len(matches),wins=sum(r['result']=='win' for r in matches),
            margin=statistics.mean(r['ours']-r['theirs'] for r in matches),
            errors=sum(r['errors'] for r in matches),faults=sum(r['faults'][r['side']] for r in matches)))
    rows.sort(key=lambda r:(-r['faults'],r['wins'],r['margin']),reverse=True)
    save(STORE/(split+'-leaderboard.json'),rows)
    for row in rows:print(json.dumps(row),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    b=sub.add_parser('build');b.add_argument('names',nargs='+');b.add_argument('--jobs',type=int,default=1)
    c=sub.add_parser('clone');c.add_argument('name');c.add_argument('--parent',default='g00');c.add_argument('--config',required=True)
    r=sub.add_parser('run');r.add_argument('label');r.add_argument('--candidates',nargs='+',required=True);r.add_argument('--opponents',nargs='+',required=True);r.add_argument('--split',choices=['screen','train','validation','holdout','broad'],required=True);r.add_argument('--maps',nargs='+');r.add_argument('--jobs',type=int,default=4)
    s=sub.add_parser('rank');s.add_argument('label')
    x=sub.add_parser('compare');x.add_argument('labels',nargs='+');x.add_argument('--baseline',default='g00')
    l=sub.add_parser('leaderboard');l.add_argument('split',choices=['train','validation'])
    args=p.parse_args()
    if args.command=='init':init()
    elif args.command=='build':build(args.names,args.jobs)
    elif args.command=='clone':create(args.name,json.loads(args.config),args.parent)
    elif args.command=='run':run(args)
    elif args.command=='rank':rank(args.label)
    elif args.command=='compare':compare(args.labels,args.baseline)
    elif args.command=='leaderboard':leaderboard(args.split)

if __name__=='__main__':main()
