"""PD03: bounded source/representation inventory, no engine queries or fits."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from ..audit import immutable_json
from ..data import digest
from ..rich_data import read_turns
from .trajectory import ROOT,OUT


def run():
    assert not (OUT/'PD03.json').exists()
    jobs_path=ROOT/'.cambc/action-predictor/v7/jobs.json'
    assert digest(jobs_path)=='80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba'
    jobs=json.loads(jobs_path.read_text())
    prior_path=ROOT/'tools/action_predictor/experiments/v8/priority-two-engine-audit.json'
    prior=json.loads(prior_path.read_text())
    assert prior['passed'] and len(prior['games'])==2
    selected=[j for j in jobs if j['record']['raw_sha256'] in prior['games']]
    assert len(selected)==2 and all(j['split']=='train' for j in selected)
    assert {j['record']['engine_version'] for j in selected}=={'2.0.0','3.0.0'}
    reader=Path('C:/Users/Subhan/.t3/worktrees/starter-python/t3-e88e3f9a/tools/replay_eval/frozen_v1_5/micro_playback.cjs')
    sources=[Path(__file__),reader,ROOT/'tools/action_predictor/priority_inputs.py',
        ROOT/'tools/action_predictor/priority_head.py',ROOT/'tools/action_predictor/entity_set.py',
        ROOT/'sdk/python/cambc/__init__.py',ROOT/'sdk/cpp/cambc.h']
    bindings={str(p):digest(p) for p in sources+[jobs_path,prior_path]}
    # Historical SDK source from repository history, without checkout changes.
    sdk_blob=subprocess.run(['git','show','0095e8e:sdk/python/cambc/__init__.py'],cwd=ROOT,
                            check=True,capture_output=True).stdout
    sdk_text=sdk_blob.decode('utf-8')
    getters=[]
    for name in ('prev_priority','priority'):
        start=sdk_text.index('    def '+name+'(')
        end=sdk_text.index('\n    def ',start+5)
        body=sdk_text[start:end]
        assert '_bc.champion_priority' in body and '_require_self' not in body
        getters.append(dict(name=name,body=body))
    immutable_json(OUT/'PD03-plan.json',dict(
        purpose='Inventory omitted other-champion scheduling fields in the two previously audited '
                'eligible TRAIN games. Not a new availability certification or predictive experiment.',
        selected_jobs=[dict(raw=j['record']['raw_sha256'],engine=j['record']['engine_version'],
                            rows=j['rows']) for j in selected],
        selection='Exactly original two-engine priority-audit games, fixed before reading their fields. '
                  'No reserved records, no new sample chosen by model error.',
        operations='Read source and existing personal observation JSON only; no engine/API query, '
                   'replay restoration, matching, fitting, new features or command predictions.',
        limitations='Current SDK or old wrapper presence alone does not prove historical engine2/3 '
                    'availability. Viewer snapshot priority fields must not be consumed as personal '
                    'features without direct historical personal-API/visibility verification.',
        bindings=bindings,historical_sdk=dict(commit='0095e8e',path='sdk/python/cambc/__init__.py',
            blob_sha256=hashlib.sha256(sdk_blob).hexdigest()),new_fits=0,reserved_opened=0))
    results=[]
    for job in selected:
        turns=read_turns(job['manifest'],job['record'])
        counts=Counter()
        champion_keys=Counter()
        own_keys=Counter()
        for turn in turns:
            for decision in turn['decisions']:
                obs=decision['observation']
                own=obs['own']
                own_keys.update(own.keys())
                counts['decisions']+=1
                known=[e for e in obs['entities'] if e['entity']['kind']==1 and e.get('known',0)&1]
                counts['known_public_other_champion_records']+=len(known)
                counts['rows_with_known_public_other_champion']+=bool(known)
                counts['rows_with_known_public_ally']+=any(e.get('team')==own.get('team') for e in known)
                counts['rows_with_known_public_enemy']+=any(e.get('team')!=own.get('team') for e in known)
                is_priority=decision['label']['root_class']=='priority'
                counts['recorded_priority_rows']+=is_priority
                counts['priority_rows_with_known_public_other_champion']+=is_priority and bool(known)
                for entity in known:
                    champion_keys.update(entity.keys())
                    for key in ('priority','nextPriority'):
                        counts['other_records_with_'+key]+=key in entity
                for key in ('priority','nextPriority'):
                    counts['original_own_records_with_'+key]+=key in own
        assert counts['decisions']==job['rows']
        record=job['record']
        path=Path(record['augmented_path']) if 'augmented_path' in record else Path(job['manifest']['source'])/'extracted'/record['raw_sha256']/'turns.jsonl'
        bindings[str(path)]=record.get('augmented_sha256',record['turns_sha256'])
        results.append(dict(engine=record['engine_version'],raw_sha256=record['raw_sha256'],
            counts=dict(counts),known_other_champion_keys=dict(champion_keys),own_keys=dict(own_keys)))
    immutable_json(OUT/'PD03.json',dict(games=results,bindings=bindings,
        protocol_sha256=digest(OUT/'PD03-plan.json'),historical_sdk_getters=getters,
        established='Original personal-observation whitelist omits priority/nextPriority for all '
                    'entities. P05 later recovers own values only. Entity tokens omit other scheduling '
                    'values. Historical checked-in wrappers contain non-self priority queries.',
        unestablished='Direct engine2/3 personal-API availability/freshness/visibility for other '
                      'champions; frequency of useful values; causal contribution to prediction errors.',
        next_correctness_check='Before features or fitting, verify scoped historical personal queries '
                               'on bounded eligible recorded PREs, distinct from viewer snapshot reads. '
                               'No hidden/omniscient values may be used.',
        engine_queries=0,new_features=0,new_predictions=0,new_fits=0,reserved_opened=0))
    print(json.dumps([{k:v for k,v in r.items() if k in ('engine','counts')} for r in results],indent=2))


if __name__=='__main__':
    run()
