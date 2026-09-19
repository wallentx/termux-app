"""Collector regressions without a device or wall-clock delays."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('capture', Path(__file__).with_name('capture.py'))
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CaptureTest(unittest.TestCase):
    def run_capture(self, metadata):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        output = Path(directory.name) / 'report'
        phases = iter(name for name in ('text_scroll', 'image_redraw', 'image_replace')
                      for _ in range(2))
        state_reads = 0
        samples = 0

        def adb(args, **kwargs):
            nonlocal state_reads, samples
            command = args[-1]
            if 'state.json' in command:
                state_reads += 1
                return json.dumps({'phase': next(phases),
                                   'state': 'ready' if state_reads % 2 else 'done'})
            if 'framestats' in command:
                samples += 1
                timestamp = ((samples - 1) % 3 + 1) * 100
                return ('---PROFILEDATA---\nFlags,IntendedVsync,FrameCompleted\n'
                        f'0,{timestamp},{timestamp + 50}\n---PROFILEDATA---')
            if 'result.json' in command:
                return metadata
            return ''

        with patch.object(capture.subprocess, 'check_output', side_effect=adb), \
             patch.object(capture.time, 'sleep'), \
             patch.object(capture.time, 'monotonic', side_effect=range(1000)), \
             patch('sys.argv', ['capture.py', '--serial', 'fake', '--remote-dir', '/run',
                                '--output', str(output)]):
            if metadata == 'incomplete':
                with self.assertRaisesRegex(TimeoutError, 'result.json'):
                    capture.main()
                self.assertFalse((output / 'summary.json').exists())
            else:
                capture.main()
                for phase in ('text_scroll', 'image_redraw', 'image_replace'):
                    frames = json.loads((output / (phase + '-frames.json')).read_text())
                    self.assertEqual([200, 300], [frame['IntendedVsync'] for frame in frames])
                self.assertEqual({'complete': True}, json.loads((output / 'workload.json').read_text()))

    def test_collects_tail_after_done(self):
        self.run_capture('{"complete": true}')

    def test_incomplete_metadata_fails_run(self):
        self.run_capture('incomplete')


if __name__ == '__main__':
    unittest.main()
