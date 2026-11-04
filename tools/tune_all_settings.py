"""Advance the complete Config sweep without discarding frozen generations.

The initial design is continuation-design.json. Each phase writes its decision
before building/running. Run phases in order: expand, combine, validate, refine, refine_expand,
refine_combine, refine_validate, pool. Use coverage to inspect explicit probes.
"""
import argparse
from collections import defaultdict
import os
import statistics
import tune_leader_party as t

COMMON=['g02_bank35','D1','gold_diamond']


def score(rows):
    return dict(games=len(rows),wins=sum(r['result']=='win' for r in rows),
                margin=statistics.mean(r['ours']-r['theirs'] for r in rows),
                faults=sum(r['faults'][r['side']] for r in rows),
                errors=sum(r['errors'] for r in rows))


def ranking(label):
    data=t.read(t.STORE/(label+'.json'))
    assert data['status']=='complete',label
    groups=defaultdict(list)
    for row in data['matches']:groups[row['candidate']].append(row)
    return {name:score(rows) for name,rows in groups.items()}


def order(result):return (-result['faults'],result['wins'],result['margin'])


def distinct(names,limit):
    registry=t.read(t.STORE/'generations.json');seen=set();result=[]
    for name in names:
        digest=registry[name]['wasm_sha256']
        if digest in seen:continue
        seen.add(digest);result.append(name)
        if len(result)==limit:break
    return result


def run(label,names,split,opponents=None,maps=None):
    t.run(argparse.Namespace(label=label,candidates=list(dict.fromkeys(names)),
          opponents=opponents or COMMON,split=split,maps=maps,jobs=8))


def freeze(filename,data):
    path=t.STORE/filename
    if path.exists():assert t.read(path)==data,'Frozen decision changed: '+filename
    else:t.save(path,data)


def build_missing(names):
    registry=t.read(t.STORE/'generations.json')
    t.build([name for name in names if 'wasm_sha256' not in registry[name]],jobs=4)


def expand_sweep(prefix,design_file):
    design=t.read(t.STORE/design_file)
    ranks=ranking(prefix+'-complete-screen')
    if prefix=='generation06' and (t.STORE/'generation06-endpoint-design.json').exists():
        extra=t.read(t.STORE/'generation06-endpoint-design.json')
        additional=ranking('generation06-endpoint-screen')
        for name,result in additional.items():
            if name in ranks:assert ranks[name]==result
        ranks.update(additional)
        design['candidates']+=extra['candidates']
    by_stat=defaultdict(list)
    for candidate in design['candidates']:
        if candidate['stat']!='attacks':by_stat[candidate['stat']].append(candidate['name'])
    selected={stat:max(names,key=lambda n:order(ranks[n])) for stat,names in by_stat.items()}
    decision=dict(selected=selected,screen_scores=ranks,policy='Expand the best probe for every active stat, including losing settings, rather than only the overall leaders. Conditional protocol settings compare against coordination enabled. Preserve the unchanged control and coordination control.')
    freeze(prefix+'-expansion.json',decision)
    run(prefix+'-complete-train',[design['control'],design['coordination_control'],*selected.values()],'train')


def expand():
    expand_sweep('generation04','continuation-design.json')


def combine_sweep(prefix,next_prefix,control,coordination_control):
    ranks=ranking(prefix+'-complete-train')
    selected=t.read(t.STORE/(prefix+'-expansion.json'))['selected']
    registry=t.read(t.STORE/'generations.json')
    base={**t.DEFAULTS,**registry[control]['config']}
    positives={}
    comparisons={}
    for stat,name in selected.items():
        ref=coordination_control if stat in ['rally_life','lease'] else control
        delta=ranks[name]['wins']-ranks[ref]['wins']
        comparisons[stat]=dict(candidate=name,reference=ref,wins_delta=delta,
            margin_delta=ranks[name]['margin']-ranks[ref]['margin'],score=ranks[name])
        if not ranks[name]['faults'] and delta>0:positives[stat]=registry[name]['config'][stat]
    # A lifetime/lease change may rescue coordination even if its default loses.
    if any(k in positives and ranks[selected[k]]['wins']>ranks[control]['wins']
           for k in ['rally_life','lease']):positives['coordination']=True
    if not positives.get('coordination',base['coordination']):
        for key in ['rally_life','lease']:positives.pop(key,None)
    if positives.get('recovery_low',base['recovery_low'])>=positives.get('recovery_high',base['recovery_high']):
        weaker=min(['recovery_low','recovery_high'],key=lambda k:comparisons[k]['wins_delta'])
        positives.pop(weaker,None)
    if positives.get('reserve',base['reserve'])>=positives.get('field_admission',base['field_admission']):
        weaker=min(['reserve','field_admission'],key=lambda k:comparisons[k]['wins_delta'])
        positives.pop(weaker,None)
    families=dict(banking=['bank_bag','bag_age','recall_gold'],
        recovery=['recovery_low','recovery_high','wards'],
        tasks=['stall','task_limit','max_clear','protection_limit','retry','competition_cost','value_routing'],
        search=[k for k in base if k.startswith('loop_')],
        fuel=['reserve','field_admission','max_fields'],
        team=['coordination','rally_life','lease'])
    proposals={'all':positives}
    strongest=sorted(positives,key=lambda k:comparisons[k]['wins_delta'],reverse=True)[:6]
    proposals['top6']={k:positives[k] for k in strongest}
    for family,keys in families.items():
        changes={k:v for k,v in positives.items() if k in keys}
        if changes:proposals[family]=changes
    # Explicitly test gated-feature interactions, including when default-on lost.
    proposals['team_probe']=dict(coordination=True,**{
        k:registry[selected[k]]['config'][k] for k in ['rally_life','lease']})
    proposals['value_probe']=dict(value_routing=True,
        competition_cost=registry[selected['competition_cost']]['config']['competition_cost'],
        loop_phase=registry[selected['loop_phase']]['config']['loop_phase'])
    # Test each whole family as well: individually losing settings can interact.
    for family,keys in families.items():
        changes={k:registry[selected[k]]['config'][k] for k in keys if k in selected}
        if family=='team':changes['coordination']=True
        if family=='recovery' and changes.get('recovery_low',base['recovery_low'])>=changes.get('recovery_high',base['recovery_high']):
            weaker=min(['recovery_low','recovery_high'],key=lambda k:comparisons[k]['wins_delta'])
            changes.pop(weaker,None)
        if family=='fuel' and changes.get('reserve',base['reserve'])>=changes.get('field_admission',base['field_admission']):
            weaker=min(['reserve','field_admission'],key=lambda k:comparisons[k]['wins_delta'])
            changes.pop(weaker,None)
        if changes:proposals[family+'_probe']=changes
    # Leave-one-family-out tests expose interactions hidden by individual screens.
    for family,keys in families.items():
        changes={k:v for k,v in positives.items() if k not in keys}
        if changes and changes!=positives:proposals['without_'+family]=changes
    for flag in ['coordination','wards','value_routing']:
        proposals['flip_'+flag]={**positives,flag:not positives.get(flag,base[flag])}
    seen=set();created={}
    for suffix,changes in proposals.items():
        if not changes:continue
        identity=tuple(sorted(changes.items()))
        if identity in seen:continue
        seen.add(identity);name=next_prefix+'_'+suffix;created[name]=changes
    decision=dict(positive_settings=positives,comparisons=comparisons,combinations=created,
        policy='Combine full-training gains with no VM faults; allow conditional settings to rescue an enabled feature when that complete probe beats the control. Test positive-setting families, top six gains, whole-family probes including individual losers, feature flips and leave-one-family-out ablations. No promotion from isolated wins alone.')
    freeze(next_prefix+'-combination-design.json',decision)
    for name,changes in created.items():
        if name not in registry:t.create(name,changes,control)
    build_missing(created)
    top_singles=sorted(set(selected.values()),key=lambda n:order(ranks[n]),reverse=True)[:4]
    run(next_prefix+'-combined-train',[control,*created,*top_singles],'train')


def combine():
    combine_sweep('generation04','g05','g04_control','g04_coordination_0')


def validate():
    ranks=ranking('g05-combined-train')
    eligible=[n for n in ranks if n!='g04_control' and not ranks[n]['faults']]
    shortlist=distinct(sorted(eligible,key=lambda n:order(ranks[n]),reverse=True),5)
    frozen=t.STORE/'generation05-validation-freeze.json'
    if frozen.exists():shortlist=t.read(frozen)['candidates']
    freeze('generation05-validation-freeze.json',dict(candidates=shortlist,training_scores=ranks,
        policy='Top five combined or single-stat profiles, selected by training wins then margin. Compare to G2 control and earlier G1/G3 winners on 18 validation maps. These existing splits are reused; no pristine holdout claim.'))
    run('generation05-combined-validation',['g04_control','g01_recover_late','g03_recover20',*shortlist],'validation')



def refine():
    train=ranking('g05-combined-train')
    valid=ranking('generation05-combined-validation')
    # G5's already-frozen shortlist contains one executable alias. Preserve that
    # receipt and add the next distinct strategy instead of rewriting history.
    unique=distinct(sorted([n for n in train if not train[n]['faults']],key=lambda n:order(train[n]),reverse=True),5)
    extra=[n for n in unique if n not in valid]
    freeze('generation05-unique-extension-design.json',dict(candidates=extra,
        policy='Preserve the frozen G5 validation receipt; add missing top-five distinct executables so an alias cannot consume a shortlist slot.'))
    if extra:
        run('generation05-unique-extension',extra,'validation')
        valid.update(ranking('generation05-unique-extension'))
    eligible=[n for n in train if n in valid and not train[n]['faults'] and not valid[n]['faults']]
    parent=max(eligible,key=lambda n:(train[n]['wins']+valid[n]['wins'],valid[n]['wins'],train[n]['margin']+valid[n]['margin']))
    registry=t.read(t.STORE/'generations.json')
    base={**t.DEFAULTS,**registry[parent]['config']}
    steps=dict(bank_bag=5,bag_age=15,stall=2,task_limit=20,max_clear=20,
        protection_limit=3,retry=3,recovery_low=.05,recovery_high=.05,
        recall_gold=100,competition_cost=2,loop_candidates=8,loop_altars=1,
        loop_beam=2,loop_length=1,loop_expansions=256,loop_reports=1,
        loop_gold=.02,loop_opening=.1,loop_risk=.1,loop_service=3,loop_phase=1,
        rally_life=3,lease=2,reserve=2500,field_admission=10000,max_fields=1)
    caps=dict(loop_candidates=48,loop_altars=255,loop_beam=32,loop_length=5,
        loop_expansions=20000,loop_reports=3,loop_phase=10,field_admission=200000)
    zero={'competition_cost','loop_gold','loop_opening','loop_risk','loop_service','loop_phase','recall_gold'}
    ranges={}
    for key,step in steps.items():
        values=[]
        for delta in [-step,step]:
            v=round(base[key]+delta,6) if isinstance(step,float) else base[key]+delta
            if v<(0 if key in zero else .05 if key.startswith('recovery_') else 1):continue
            if v>caps.get(key,float('inf')):continue
            if key=='recovery_low' and v>=base['recovery_high']:continue
            if key=='recovery_high' and v>=1:continue
            if key=='recovery_high' and v<=base['recovery_low']:continue
            if key=='reserve' and v>=base['field_admission']:continue
            if key=='field_admission' and v<=base['reserve']:continue
            values.append(v)
        ranges[key]=values
    incumbent={**t.DEFAULTS,**registry['g02_bank35']['config']}
    reversions={}
    for key in steps:
        v=incumbent[key]
        if v==base[key]:continue
        if key=='recovery_low' and v>=base['recovery_high']:continue
        if key=='recovery_high' and v<=base['recovery_low']:continue
        if key=='reserve' and v>=base['field_admission']:continue
        if key=='field_admission' and v<=base['reserve']:continue
        ranges[key]=sorted(set(ranges[key]+[v]))
        reversions[key]=v
    proven=t.read(t.STORE/'g05-combination-design.json')['positive_settings']
    for key,v in proven.items():
        if key not in steps or v==base[key]:continue
        if key=='recovery_low' and v>=base['recovery_high']:continue
        if key=='recovery_high' and v<=base['recovery_low']:continue
        if key=='reserve' and v>=base['field_admission']:continue
        if key=='field_admission' and v<=base['reserve']:continue
        ranges[key]=sorted(set(ranges[key]+[v]))
    # Four altars is an adapter default, not a serialization limit. Exercise
    # larger widths in the combined parent's context, without changing G4/G5.
    ranges['loop_altars']=sorted(set(ranges['loop_altars']+[8,16])-{base['loop_altars']})
    wider_search=dict(loop_candidates=[48],loop_beam=[16,32],loop_expansions=[6144,20000])
    for key,values in wider_search.items():
        ranges[key]=sorted(set(ranges[key]+values)-{base[key]})
    for key in ['wards','value_routing','coordination']:ranges[key]=[not base[key]]
    items=[]
    for key,values in ranges.items():
        for i,v in enumerate(values):
            name=f'g06_{key}_{i}';changes={key:v}
            if key in ['rally_life','lease']:changes['coordination']=True
            items.append(dict(name=name,stat=key,value=v,context=changes))
    coord=parent if base['coordination'] else 'g06_coordination_0'
    design=dict(control=parent,coordination_control=coord,candidates=items,ranges=ranges,
        incumbent_reversions=reversions,
        earlier_training_gains=proven,
        wider_search_probes=wider_search,
        training_scores=train,validation_scores=valid,
        policy='Second independent sweep of every active stat around the strongest combined training/validation profile. Smaller steps refine interiors and extend promising outer boundaries where safe; explicitly revert changed stats to incumbent G2 values to test interactions. Add 8/16 retained altars: source inspection shows the four-altar default is not a packet cap; the mask supports 255. Toggle booleans again; exercise protocol settings with coordination enabled. attacks remains unused and byte-identical.')
    freeze('generation06-design.json',design)
    for item in items:
        if item['name'] not in registry:t.create(item['name'],item['context'],parent)
    build_missing([item['name'] for item in items])
    run('generation06-complete-screen',[parent,coord,*[i['name'] for i in items]],'screen')


def refine_expand():
    parent=t.read(t.STORE/'generation06-design.json')['control']
    settings=dict(recovery_low=0.0,recovery_high=1.0,loop_risk=1.0,reserve=0,
        protection_limit=0,retry=0,rally_life=0,lease=0)
    items=[]
    for key,value in settings.items():
        context={key:value}
        if key in ['rally_life','lease']:context['coordination']=True
        items.append(dict(name='g06e_'+key,stat=key,value=value,context=context))
    freeze('generation06-endpoint-design.json',dict(control=parent,candidates=items,
        policy='Test legal recovery/risk endpoints and zero action reserve in the combined parent context. Preserve the main frozen screen. Faults disqualify promotion; endpoint probes join the same per-stat full-training selection.'))
    registry=t.read(t.STORE/'generations.json')
    for item in items:
        if item['name'] not in registry:t.create(item['name'],item['context'],parent)
    build_missing([i['name'] for i in items])
    run('generation06-endpoint-screen',[parent,*[i['name'] for i in items]],'screen')
    expand_sweep('generation06','generation06-design.json')


def refine_combine():
    design=t.read(t.STORE/'generation06-design.json')
    combine_sweep('generation06','g07',design['control'],design['coordination_control'])




def refine_validate():
    ranks=ranking('g07-combined-train')
    eligible=[n for n in ranks if not ranks[n]['faults']]
    shortlist=distinct(sorted(eligible,key=lambda n:order(ranks[n]),reverse=True),5)
    prior=t.read(t.STORE/'generation06-design.json')['control']
    freeze('generation07-validation-freeze.json',dict(candidates=shortlist,parent=prior,training_scores=ranks,
        policy='Validate the top five second-sweep combinations or independent winners, preserving the combined parent, G2 and G1/G3 controls.'))
    run('generation07-combined-validation',[prior,'g04_control','g01_recover_late','g03_recover20',*shortlist],'validation')


def pool():
    prior=t.read(t.STORE/'generation06-design.json')['control']
    train=ranking('g07-combined-train');valid=ranking('generation07-combined-validation')
    eligible=[n for n in train if n in valid and not train[n]['faults'] and not valid[n]['faults']]
    finalists=distinct(sorted(eligible,key=lambda n:(train[n]['wins']+valid[n]['wins'],valid[n]['wins'],train[n]['margin']+valid[n]['margin']),reverse=True),2)
    earlier_train=ranking('g05-combined-train')
    earlier_valid=ranking('generation05-combined-validation')
    if (t.STORE/'generation05-unique-extension.json').exists():
        earlier_valid.update(ranking('generation05-unique-extension'))
    earlier_eligible=[n for n in earlier_train if n in earlier_valid and not earlier_train[n]['faults'] and not earlier_valid[n]['faults']]
    earlier=distinct(sorted(earlier_eligible,key=lambda n:(earlier_train[n]['wins']+earlier_valid[n]['wins'],earlier_valid[n]['wins'],earlier_train[n]['margin']+earlier_valid[n]['margin']),reverse=True),2)
    candidates=list(dict.fromkeys([*finalists,prior,*earlier,'g02_bank35','g03_recover20']))
    registry=t.read(t.STORE/'generations.json')
    # Identical executables are aliases, not independent contenders.
    seen=set();unique=[]
    for name in candidates:
        digest=registry[name]['wasm_sha256']
        for canonical in ['g02_bank35','g03_recover20']:
            if digest==registry[canonical]['wasm_sha256']:name=canonical;break
        if digest in seen:continue
        seen.add(digest);unique.append(name)
    freeze('complete-tuning-finalists.json',dict(candidates=unique,finalists=finalists,parent=prior,earlier_generation_finalists=earlier,
        source_and_artifact={n:registry[n] for n in unique},
        policy='All candidates frozen before this full-pool comparison. Final choice uses common-opponent wins, no VM faults; direct ancestry and the wider suite inform near-tie judgment. The published pool is adaptive selection evidence. Reserved legacy maps are evaluated only after the final configuration is selected.'))
    splits=t.read(t.STORE/'experiment.json')['splits']
    maps=splits['train']+splits['validation']+splits['holdout']
    run('complete-tuning-published-pool',unique,'broad',['subhan','D1','gold_diamond'],maps)
    broad=['00ambush','00expanse','00interlock','00lanes','00monolith','00packs']
    run('complete-tuning-opponent-pool',unique,'broad',[f'pool{i}' for i in range(15)],broad)
    ancestors=list(dict.fromkeys(['g02_bank35','g01_recover_late','g03_recover20',prior,*earlier]))
    run('complete-tuning-ancestry',unique,'validation',ancestors)


def targeted():
    """Final interaction probes, preserving the already frozen pool receipts."""
    parent='g07_search'
    proposals=dict(g08_phase4=dict(loop_phase=4),g08_phase5=dict(loop_phase=5),
        g08_comp6=dict(competition_cost=6),g08_comp8=dict(competition_cost=8),
        g08_retry0=dict(retry=0),g08_comp6_retry0=dict(competition_cost=6,retry=0))
    freeze('generation08-targeted-design.json',dict(parent=parent,candidates=proposals,
        policy='Final targeted refinement frozen before the 86-map pool results: extend the strongest validated planner-start value 3 to 4/5; combine that parent with the independently supported competition penalty 6 and adjacent 8, and zero-retry training winner. Test the small combination separately from the regressing full G7 combination. No other fields change.'))
    registry=t.read(t.STORE/'generations.json')
    for name,changes in proposals.items():
        if name not in registry:t.create(name,changes,parent)
    build_missing(proposals)
    from finalize_config_tuning import native
    native(('g08_',),'generation08-native.json')
    run('generation08-targeted-train',[parent,*proposals],'train')
    run('generation08-targeted-validation',[parent,*proposals],'validation')
    train=ranking('generation08-targeted-train');valid=ranking('generation08-targeted-validation')
    ordered=sorted(proposals,key=lambda n:(train[n]['wins']+valid[n]['wins'],valid[n]['wins'],
        train[n]['margin']+valid[n]['margin']),reverse=True)
    selected=distinct([n for n in ordered if not train[n]['faults'] and not valid[n]['faults']],2)
    freeze('generation08-finalists.json',dict(candidates=selected,training=train,validation=valid,
        policy='Best two distinct fault-free final targeted probes by pooled train/validation wins, then validation wins and combined margin. Compare on the identical final matrices; do not replace any prior frozen receipts.'))
    splits=t.read(t.STORE/'experiment.json')['splits']
    run('targeted-tuning-published-pool',selected,'broad',['subhan','D1','gold_diamond'],
        splits['train']+splits['validation']+splits['holdout'])
    run('targeted-tuning-opponent-pool',selected,'broad',[f'pool{i}' for i in range(15)],
        ['00ambush','00expanse','00interlock','00lanes','00monolith','00packs'])
    prior=t.read(t.STORE/'complete-tuning-finalists.json')
    ancestors=list(dict.fromkeys(['g02_bank35','g01_recover_late','g03_recover20',prior['parent'],*prior['earlier_generation_finalists']]))
    run('targeted-tuning-ancestry',selected,'validation',ancestors)
    coverage()


def coverage():
    """Report explicit independent/conditional probes, not incidental config values."""
    registry=t.read(t.STORE/'generations.json')
    completed={}
    for path in t.STORE.glob('*.json'):
        data=t.read(path)
        if not isinstance(data,dict) or data.get('status')!='complete':continue
        for row in data.get('matches',[]):
            key=(row['candidate'],row['opponent'],row['map'],row['side'])
            if key in completed:assert completed[key]==row,'Conflicting repeated result'
            completed[key]=row
    by_name=defaultdict(list)
    for row in completed.values():by_name[row['candidate']].append(row)
    designs=[t.read(t.STORE/'continuation-design.json')]
    if (t.STORE/'generation06-design.json').exists():designs.append(t.read(t.STORE/'generation06-design.json'))
    if (t.STORE/'generation06-endpoint-design.json').exists():designs.append(t.read(t.STORE/'generation06-endpoint-design.json'))
    if (t.STORE/'generation08-targeted-design.json').exists():
        targeted=t.read(t.STORE/'generation08-targeted-design.json')
        items=[dict(name=name,stat=key,value=value,context=context)
            for name,context in targeted['candidates'].items() for key,value in context.items()]
        designs.append(dict(candidates=items))
    inventory={k:dict(default=v,probes=[]) for k,v in t.DEFAULTS.items()}
    for design in designs:
        for item in design['candidates']:
            name=item['name'];rows=by_name[name]
            inventory[item['stat']]['probes'].append(dict(name=name,value=item['value'],
                parent=registry[name]['parent'],context=item['context'],
                built='wasm_sha256' in registry[name],score=score(rows) if rows else None))
    assert all(v['probes'] for v in inventory.values())
    inventory['attacks']['interpretation']='Unused declaration; no callers. Both values compile to exactly the same WASM. No runtime tuning is possible without an algorithm change.'
    for key in ['rally_life','lease']:
        inventory[key]['interpretation']='Measured with coordination enabled; compare against the coordination-enabled control. Dormant when coordination is disabled.'
    t.save(t.STORE/'all-settings-coverage.json',dict(settings=len(inventory),
        oriented_conditions=len(completed),inventory=inventory,
        policy='Probes list independent changes and explicitly enabled contexts. Scores deduplicate repeated candidate/opponent/map/side conditions. This coverage report is descriptive and does not itself establish final selection.'))
    print('Coverage:',len(inventory),'settings;',len(completed),'oriented conditions',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['expand','combine','validate','refine','refine_expand','refine_combine','refine_validate','pool','targeted','coverage']);args=p.parse_args()
    os.environ.setdefault('CMAKE_BUILD_PARALLEL_LEVEL','2')
    globals()[args.phase]()

if __name__=='__main__':main()
