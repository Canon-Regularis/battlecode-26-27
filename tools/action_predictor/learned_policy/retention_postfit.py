"""Registered L02 diagnostic pipeline, no training or optimizer operations."""
from . import (analysis, matched_movement, retention_evaluate, natural_evaluation,
    components, dominance_bounds, retention_memory, retention_report)


def run():
    stages=[('category/sequence analysis',lambda:analysis.run('L02')),
        ('matched movement',lambda:matched_movement.run('L02')),
        ('direct L01 comparison and checkpoint contract',retention_evaluate.run),
        ('natural-cadence evaluation',lambda:natural_evaluation.run('L02')),
        ('DEV component execution',lambda:components.run('L02','validation')),
        ('DEV fixed-distribution bound',lambda:dominance_bounds.run('L02','validation')),
        ('TRAIN component execution',lambda:components.run('L02','train')),
        ('TRAIN fixed-distribution bound',lambda:dominance_bounds.run('L02','train')),
        ('DEV direct gate/decay features',lambda:retention_memory.run('L02','validation')),
        ('TRAIN direct gate/decay features',lambda:retention_memory.run('L02','train')),
        ('saved-result report',retention_report.run)]
    for label,function in stages:
        print('L02 diagnostics starting:',label,flush=True);function()
        print('L02 diagnostics completed:',label,flush=True)


if __name__=='__main__':run()
