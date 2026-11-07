"""Payload identity and whole-group selection tests; no network or behaviour reads."""
import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.action_predictor import more_replays as collector


class MoreReplayTests(unittest.TestCase):
    def test_payload_dedup_ignores_zip_container_and_handles_nested_bundle(self):
        raw=b'a62per\0\0\x03\0\0same recorded bytes'
        with tempfile.TemporaryDirectory() as directory:
            first=Path(directory)/'one.repl26a';second=Path(directory)/'archive.zip'
            with zipfile.ZipFile(first,'w',compression=zipfile.ZIP_STORED) as z:z.writestr('replay.repl26a',raw)
            nested=io.BytesIO()
            with zipfile.ZipFile(nested,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('replay.repl26a',raw)
            with zipfile.ZipFile(second,'w') as z:z.writestr('nested.repl26a',nested.getvalue())
            a,ae=collector.payloads(first);b,be=collector.payloads(second)
            self.assertFalse(ae or be)
            self.assertEqual(a[0]['sha256'],b[0]['sha256'])
            self.assertEqual(a[0]['sha256'],hashlib.sha256(raw).hexdigest())

    def test_known_member_excludes_entire_group_and_incomplete_groups_are_rejected(self):
        matches=[]
        for group in range(126):
            for position in range(1,6 if group<125 else 5):
                matches.append(dict(matchId=f'01a1b172-{group:04x}-71d6-aec1-e0dc92bcf38{position}',
                    groupId=f'group-{group}',position=position,kind='ranked',status='finished',
                    createdAt='2026-11-06T12:00:00Z',teams=[dict(teamId=collector.FISH)]))
        existing=dict(entries=[dict(match_ids=[matches[0]['matchId']])])
        with tempfile.TemporaryDirectory() as directory,patch.object(collector,'WORK',Path(directory)), \
             patch.object(collector,'api',return_value=dict(matches=matches,nextCursor=None)), \
             contextlib.redirect_stdout(io.StringIO()):
            result=collector.candidates(existing,['cli'])
        names={g['group'] for g in result['groups']}
        self.assertNotIn('group-0',names);self.assertNotIn('group-125',names)
        self.assertEqual(len(names),124)
        self.assertTrue(all(len(g['matches'])==5 for g in result['groups']))


if __name__=='__main__':unittest.main()
