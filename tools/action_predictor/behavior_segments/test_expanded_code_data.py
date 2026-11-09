import unittest
from . import expanded_code_data as expanded
from . import data


class ExpandedCodeDataTests(unittest.TestCase):
    def test_paths_restore_after_failure(self):
        original=(data.REPORT,data.WORK)
        with self.assertRaises(RuntimeError):
            with expanded.assembly_paths():
                self.assertEqual((data.REPORT,data.WORK),(expanded.REPORT,expanded.WORK))
                raise RuntimeError('synthetic failure')
        self.assertEqual((data.REPORT,data.WORK),original)

    def test_evaluation_jobs_excluded_and_overlap_rejected(self):
        jobs=[dict(group=f'g{i}',payload=f'p{i}',partition='fit') for i in range(32)]
        jobs.append(dict(group='held',payload='held',partition='evaluation'))
        receipt=dict(groups=[dict(**j,candidates=24) for j in jobs])
        selected,counts=expanded.fit_jobs(dict(jobs=jobs),receipt)
        self.assertEqual(len(selected),32);self.assertNotIn('held',counts)
        jobs[-1]['group']='g0'
        with self.assertRaises(ValueError):expanded.fit_jobs(dict(jobs=jobs),receipt)


if __name__=='__main__':unittest.main()
