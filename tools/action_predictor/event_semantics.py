"""D01: TRAIN-only recorded root/effect/channel semantics; no predictor fit."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse,json,subprocess,sys
import numpy as np
from .category_study import ROOT,WORK,REPORTS
from .more_replays import frozen,sha
from .priority_fit_v3 import read,log,BASE
from .priority_residual_fit import verify_protocol as verify_parent
from .rich_data import read_turns
from .audit import cursor
from .data import action_name
from . import reliable_train as rt

PLAN=REPORTS/'event-semantics-plan.json'
NAMES=('event_semantics.py','event_semantics.cjs','test_event_semantics.py')
ROOTS={4:'move',5:'attack',6:'cast',8:'end',9:'priority',11:'recall',12:'submit',13:'shop',14:'ward',15:'consumable',16:'cancel',20:'altar',21:'teleport',23:'blocked',25:'sell',26:'rollover',27:'error',24:'resign'}

def classification(step):
    if step['substep']>0:return 'effect'
    if step['actor']['kind']!=1 or step['phase']!=10:return 'system'
    return ROOTS.get(step['kind'],'unknown_root')

def earlier(previous,current):
    if previous is not None:
        assert previous['actor']==current['actor']
        assert cursor(previous['event'])<=cursor(current['pre'])<cursor(current['event'])

def sources():return {str(Path(__file__).with_name(n)):sha(Path(__file__).with_name(n)) for n in NAMES}

def run():
    verify_parent();review=read(REPORTS/'P05-review.json');assert review['verdict']=='APPROVE'
    for file,key in (('P05.json','fit_report_sha256'),('P05-analysis.json','analysis_sha256'),('P05-tail-and-gate-note.json','tail_note_sha256')):assert sha(REPORTS/file)==review[key]
    jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json';jobs=[j for j in read(jobs_path) if j['split']=='train']
    chain_path=REPORTS/'priority-chain-verification.json';chain=read(chain_path)
    assert sha(chain_path)==read(REPORTS/'priority-data-review-approval.json')['chain_sha256']
    runtime_lock=read(ROOT/'tools/action_predictor/experiments/v7/execution-lock.json')
    for path,digest in runtime_lock['runtime_assets'].items():assert sha(path)==digest
    for path,digest in runtime_lock['training_sources'].items():
        if 'replay_eval' in path:assert sha(path)==digest
    assert len(jobs)==470 and len({j['record']['group'] for j in jobs})==94
    assert len({j['record']['raw_sha256'] for j in jobs})==470 and sum(j['rows'] for j in jobs)==433071
    frozen(PLAN,dict(id='D01',purpose='TRAIN-only audit of end/cancel/priority roots versus automatic effects before any action constraints or classifier experiment',
        source_hashes=sources(),P05_review_sha256=sha(REPORTS/'P05-review.json'),jobs_sha256=sha(jobs_path),train_sha256=sha(BASE/'combined-train.npz'),
        budget='All470eligibleTRAIN indexes/effect indexes and433071originalTRAIN target PREs; first target end,priority,recall,cancel in first TRAIN game per engine2/3 for eight read-only PRE/POST probes. No fits, new features, validation-behavior analysis, new labels or constraints.',
        definitions='Root is personal champion-phase substep0 input advancement; automatic substeps remain effects. Preserve original complete/censored membership and labels. Reason0 means pinned-codec Yielded, not independently established explicit API origin. Current SDK4 and visualiser wrapper are evidence with historical limitations, not proof of engine2/3 bot caller origin.',
        reporting='Counts by engine/root/reason/completeness, priority continuation and personally observable channel/flag context, full-own-index prior-event adjacency. Missing channel explicit. Effect kind16counts distinguished from rootcancel. PRE/POST diagnostics never features. No measured prediction-quality improvement inferred.',
        guards='All old splits,wholegroups,duplicates,studies,checkpoints,90%everycategory/three-seed andoriginaltargets unchanged. Both75reservedpartitions sealed;no old exposedtest;no download/matches/botchanges/deploy/PR operations. Stop for fresh Solxhigh review after completed audit.'))
    directory=WORK/'event-semantics';directory.mkdir(exist_ok=True)
    assert not (REPORTS/'D01.json').exists(),'Completed diagnostic immutable'
    for path,digest in sources().items():
        p=directory/(digest+'_'+Path(path).name)
        if not p.exists():p.write_bytes(Path(path).read_bytes())
        assert sha(p)==digest
    with np.load(BASE/'combined-train.npz') as z:train_y=z['y']
    with np.load(WORK/'priority-train.npz') as z:priorities=z['values']
    counters=defaultdict(Counter);bindings=[];examples={};probe_queries=[];total=0
    for number,job in enumerate(jobs,1):
        record=job['record'];raw=record['raw_sha256'];engine=record['engine_version'];folder=Path(job['manifest']['source'])/'extracted'/raw
        receipt=read(folder/'receipt.json');paths={name:folder/name for name in ('index.jsonl','effects.jsonl')}
        for name,path in paths.items():assert sha(path)==receipt['files'][name]
        priority_folder=WORK/'priority'/raw
        assert sha(priority_folder/'receipt.json')==chain['per_game_receipts'][raw]
        recovered=read(priority_folder/'receipt.json')
        assert recovered['raw_sha256']==raw and recovered['split']=='train' and recovered['engine']==engine and recovered['rows']==job['rows']
        assert recovered['index_sha256']==receipt['files']['index.jsonl'] and recovered['target_shard_sha256']==job['shard_sha256']
        raw_path=Path(job['work'])/'supplement'/raw/'raw.bin';assert sha(raw_path)==raw
        assert sha(job['shard'])==job['shard_sha256']
        turns=read_turns(job['manifest'],record);actors={t['actor'] for t in turns};teams={t['view']['team'] for t in turns};assert len(teams)==1;team=next(iter(teams))
        metadata={};previous={};complete_counts=Counter();footer=None
        for line in paths['index.jsonl'].open(encoding='utf-8'):
            turn=json.loads(line)
            if turn.get('record')=='index_receipt':footer=turn;continue
            if turn.get('record')!='turn' or turn['actor'] not in actors:continue
            complete_counts['complete' if turn['complete'] else 'censored']+=1
            for index,root in enumerate(turn['roots']):
                step=root['header']['step'];name=classification(step);assert name==root['classification']
                assert step['actor']==dict(kind=1,index=turn['actor']) and step['phase']==10 and step['substep']==0
                assert cursor(root['pre'])<cursor(root['event']) and cursor(root['event'])==(cursor(root['pre'])[0]+1,0)
                meta=dict(actor=turn['actor'],round=turn['round'],turn=turn['id'],event=root['event'],pre=root['pre'],classification=name,previous=previous.get(turn['actor']))
                earlier(meta['previous'],meta)
                # Only minimal predecessor metadata retained: no linked chains.
                previous[turn['actor']]={k:v for k,v in meta.items() if k!='previous'}
                assert root['event'] not in metadata;metadata[root['event']]=meta
                counters[engine]['root/'+name]+=1
                counters[engine]['root_header_phase/'+name+'/'+str(root['header']['phase'])]+=1
                if step['kind'] in (8,26,27):counters[engine]['terminal_reason/'+name+'/'+str(step.get('endTurnReason','missing'))]+=1
                if name=='priority':
                    following=turn['roots'][index+1]['classification'] if index+1<len(turn['roots']) else 'no_later_root_in_turn'
                    counters[engine]['priority_next_same_turn/'+following]+=1
        assert footer and footer['status']=='complete'
        roster={r['entity']['index']:r['team'] for r in footer['roster']}
        assert actors=={a for a,t in roster.items() if t==team},'Actor coverage must include entire Fish team'
        for key,value in complete_counts.items():counters[engine]['own_turns/'+key]+=value
        for line in paths['effects.jsonl'].open(encoding='utf-8'):
            effect=json.loads(line);assert len(effect)==10 and effect[3]>0
            if effect[6]==1 and effect[7] in actors and effect[5] in (8,9,16):counters[engine]['effect_kind_phase/'+str(effect[5])+'/'+str(effect[4])]+=1
        targets=[(t,d) for t in turns for d in t['decisions']];assert len(targets)==job['rows']
        candidates=[]
        for local,(turn,decision) in enumerate(targets):
            row=job['offset']+local;label=action_name(decision['label']);assert rt.LABELS[int(train_y[row])]==label
            meta=metadata[decision['event_cursor']];assert meta['actor']==turn['actor'] and meta['pre']==decision['pre_cursor'] and meta['round']==turn['round']
            assert classification(decision['audit']['header']['step'])==meta['classification']
            own=decision['observation']['own'];channel=own.get('channelType','unknown')
            if channel!='unknown':assert own['known']&4
            counters[engine]['target/'+label]+=1;counters[engine]['target_channel/'+label+'/'+str(channel)]+=1
            if label in ('end','cancel','priority','recall','ward'):
                prior=meta['previous'];same=prior is not None and prior['turn']==meta['turn']
                counters[engine]['target_previous_same_turn/'+label+'/'+(prior['classification'] if same else 'none')]+=1
                counters[engine]['target_priority_relation/'+label+'/'+('different' if priorities[row,1] and priorities[row,3] and priorities[row,0]!=priorities[row,2] else 'equal' if priorities[row,1] and priorities[row,3] else 'unknown')]+=1
            if label in ('end','priority','recall','cancel') and label not in {c['label'] for c in candidates}:
                candidates.append(dict(label=label,id=decision['id'],actor=turn['actor'],pre=decision['pre_cursor'],event=decision['event_cursor'],header=decision['audit']['header']))
        if engine not in examples:
            assert {c['label'] for c in candidates}=={'end','priority','recall','cancel'}
            query_path=priority_folder/'query.json'
            assert sha(query_path)==recovered['files']['query.json']
            assert sha(priority_folder/'node-receipt.json')==recovered['files']['node-receipt.json']
            assert read(priority_folder/'node-receipt.json')['query_sha256']==sha(query_path)
            query=read(query_path)
            assert str(Path(query['reader'])/'frozen_v1_5/micro_playback.cjs') in runtime_lock['training_sources']
            assert str(Path(query['assets'])/'index-B7p3Cpbd.js') in runtime_lock['runtime_assets']
            q=dict(raw=str(raw_path),raw_sha256=raw,reader=query['reader'],assets=query['assets'],team=team,samples=candidates,output=str(directory/('probe-'+engine+'.json')))
            query_path=directory/('probe-query-'+engine+'.json');frozen(query_path,q);probe_queries.append(query_path);examples[engine]=raw
        bindings.append(dict(raw_sha256=raw,group=record['group'],engine=engine,rows=job['rows'],offset=job['offset'],receipt_sha256=sha(folder/'receipt.json'),index_sha256=receipt['files']['index.jsonl'],effects_sha256=receipt['files']['effects.jsonl'],target_shard_sha256=job['shard_sha256']))
        total+=len(targets)
        if number%25==0 or number==len(jobs):print('D01 verified TRAIN evidence',number,'/',len(jobs),flush=True)
    assert total==433071
    probes=[]
    for path in probe_queries:
        command=['node',str(Path(__file__).with_name('event_semantics.cjs')),str(path)]
        log(command);process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=120)
        assert process.returncode==0,process.stderr[-2500:]
        q=read(path);output=read(q['output']);assert output['split']=='train' and len(output['rows'])==4
        probes.append(dict(query_path=str(path),query_sha256=sha(path),output_path=q['output'],output_sha256=sha(q['output']),engine=output['version'],data=output))
    from .observation_validate import sealed_audit
    sealed_audit()
    # Bind the static decoder semantics and version-limited current SDK evidence.
    q=read(probe_queries[0]);reader=Path(q['reader'])/'frozen_v1_5';assets=Path(q['assets'])
    static=[reader/'micro_playback.cjs',reader/'playback.cjs',assets/'index-B7p3Cpbd.js',assets/'PanelChrome-DRtW3oWL.js',assets/'v2_0_0-hWOQ1R8f.wasm',assets/'v3_0_0-DBS2ESWO.wasm',ROOT/'sdk/python/cambc/__init__.py']
    assert read(PLAN)['source_hashes']==sources(),'Source changed during diagnostic'
    frozen(REPORTS/'D01.json',dict(plan_sha256=sha(PLAN),source_hashes=sources(),P05_review_sha256=sha(REPORTS/'P05-review.json'),bindings=bindings,static_source_hashes={str(p):sha(p) for p in static},
        target_rows=total,train_games=len(jobs),train_groups=94,statistics={key:dict(sorted(c.items())) for key,c in counters.items()},probes=probes,
        conclusions_scope='Recorded roots/effects and personal-PRE contexts only; current SDK and visualiser names do not prove historical caller origin. No automatic constraint or prediction-quality improvement is established.',
        new_fits=0,new_features=0,all_original_targets_retained=True,reserved_behavior_opened=0,all_category_goal_met=False))
    print('D01 TRAIN-only semantics audit complete. STOP for fresh Sol xhigh review.',flush=True)

if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args();log([sys.executable,'-m','tools.action_predictor.event_semantics']);run()
