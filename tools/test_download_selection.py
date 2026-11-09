"""Focused tests for explicit cross-map downloader selections."""
import json
from pathlib import Path
import tempfile
import unittest
from download_replays import selected_matches


class SelectionTests(unittest.TestCase):
    def test_team_identity_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'selection.json'
            match=dict(matchId='01a1b172-0001-71d6-aec1-e0dc92bcf385',status='finished',teams=[dict(teamId='team-id',name='Fish')])
            path.write_text(json.dumps(dict(matches=[match])))
            self.assertEqual(list(selected_matches(path,'team-id')),[match])
            with self.assertRaises(ValueError):list(selected_matches(path,'Other'))
            path.write_text(json.dumps([match,match]))
            with self.assertRaises(ValueError):list(selected_matches(path,'Fish'))


if __name__=='__main__':unittest.main()
