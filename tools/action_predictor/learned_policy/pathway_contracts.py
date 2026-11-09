"""Check archived intervention semantics before trusting joint metrics."""
import json
import numpy as np
from .sequence_data import BASE,WORK
from .pathway_protocol import LOCAL,OUT
from .analysis import read
from ..audit import immutable_json
from ..data import digest


def run():
    with np.load(BASE.parent/'v4/validation.npz') as z:y=z['y'];py=z['py']
    results={}
    for identifier in ('L01','L02'):
        ready_path=OUT/f'Q01-{identifier}-ready-v2.json';ready=json.loads(ready_path.read_text())
        rows={}
        for name,expected in ready['branches'].items():
            path=LOCAL/f"Q01-v2/{identifier}/{name.replace('/','--')}-predictions.npz"
            assert digest(path)==expected['predictions_sha256']
            p=read(path);typed=(p['prediction']==y)&(py>=0)
            mismatch=typed&(p['coordinate']!=p['proposed_coordinate'])
            rows[name]=dict(rows=len(y),typed_spatial_rows=int(typed.sum()),
                conditional_vs_actual_argument_mismatch_rows=np.flatnonzero(mismatch).tolist(),
                finite_observed_loss=bool(np.isfinite(p['nll']).all()),
                interpretation='Joint scoring may reuse true-family diagnostic coordinates ONLY when these match the actual selected command on correctly typed rows. Any mismatch must be resolved/reported before summary metrics are trusted; never silently choose the favorable argument.')
        results[identifier]=dict(branches=rows,ready_sha256=digest(ready_path))
    immutable_json(OUT/'Q01-artifact-contracts.json',dict(results=results,source_sha256=digest(__file__),
        new_fits=0,reserved_opened=0))
    print('Q01 argument invariants', {m:{b:len(v['conditional_vs_actual_argument_mismatch_rows']) for b,v in r['branches'].items()} for m,r in results.items()},flush=True)


if __name__=='__main__':run()
