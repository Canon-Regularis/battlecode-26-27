"""Current decoded-mode ceilings only; never predictor inputs or routing."""
import json
import sys
from .sequence_data import REPORT
from ..audit import immutable_json


def run(identifier):
    d=json.loads((REPORT/f'{identifier}.json').read_text())
    categories=d['results']['validation']['all']['per_category'];n=d['results']['validation']['all']['rows']
    perfect_params=0;perfect_type=0
    for row in categories:
        if row['action']=='shop':continue
        perfect_params+=row['type_TP']
        accuracy=row['all_true_family_parameter_accuracy']
        perfect_type+=row['support'] if accuracy is None else round(row['support']*accuracy)
    immutable_json(REPORT/f'{identifier}-current-mode-oracles.json',dict(rows=n,
        perfect_required_arguments_with_current_type_choices=perfect_params,
        perfect_family_decision_with_current_conditional_modes=perfect_type,
        qualification='Postprediction current-forecast ceilings only: freeze current saved type choices or conditional argument modes. No oracle inputs/routing enter causal predictions or state. Not architecture/data ceilings; all43shop commands remain strict failures, sparse categories/identity uncertified.',
        new_fits=0,reserved_opened=0))


if __name__=='__main__':run(sys.argv[1])
