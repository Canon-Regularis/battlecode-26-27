"""Sequential, interruption-resilient execution of the bounded frozen study."""
import json
import subprocess
import sys

from .observation_study import ROOT,WORK,REPORTS,log_command


def run():
    assert (REPORTS/'data-ready.json').exists(),'Personal-history recovery must finish first'
    stages=[('observation_validate',[]),('observation_train',[]),('observation_roundtrip',None),('observation_report',[])]
    for module,arguments in stages:
        if arguments is None:
            ledger=json.loads((WORK/'fit-ledger.json').read_text())
            arguments=[name for name,fit in sorted(ledger.items()) if fit['status']=='complete']
            assert len(arguments) in (2,6)
        command=[sys.executable,'-m','tools.action_predictor.'+module,*arguments]
        (WORK/'pipeline-progress.json').write_text(json.dumps(dict(stage=module,command=command),indent=2),encoding='utf-8')
        print('STAGE',module,' '.join(arguments),flush=True)
        subprocess.run(command,cwd=ROOT,check=True)
    (WORK/'pipeline-progress.json').write_text(json.dumps(dict(stage='complete')),encoding='utf-8')


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_pipeline'],purpose='Run frozen validation, bounded fitting, inference verification and measured reporting sequentially')
    run()
