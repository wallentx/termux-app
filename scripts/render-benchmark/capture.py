#!/usr/bin/env python3
"""ADB collector for workload.py. Saves raw gfxinfo plus bounded frame samples."""
import argparse
import csv
import io
import json
from pathlib import Path
import shlex
import subprocess
import time


def parse_frames(text):
    frames = {}
    for block in text.split('---PROFILEDATA---')[1::2]:
        for row in csv.DictReader(io.StringIO(block.strip())):
            try:
                if int(row['Flags']) == 0:
                    frames[int(row['IntendedVsync'])] = {k: int(v) for k, v in row.items() if k and v}
            except (KeyError, ValueError, TypeError):
                continue
    return frames


def percentile(values, p):
    values = sorted(values)
    return round(values[min(len(values)-1, int((len(values)-1)*p))], 3) if values else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', required=True)
    parser.add_argument('--remote-dir', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)

    def adb(command):
        return subprocess.check_output(['adb', '-s', args.serial, 'shell', command], text=True, timeout=15)

    def app(command):
        return adb('run-as com.termux /system/bin/sh -c ' + shlex.quote(command))

    def state():
        try:
            return json.loads(app('cat ' + shlex.quote(args.remote_dir + '/state.json')))
        except (ValueError, subprocess.CalledProcessError):
            return {}

    def touch(suffix):
        app('touch ' + shlex.quote(args.remote_dir + '/' + suffix))

    summaries = []
    (args.output / 'device.txt').write_text(adb('getprop ro.product.model; getprop ro.build.fingerprint; dumpsys package com.termux | grep versionName'))
    for phase in ('text_scroll', 'image_redraw', 'image_replace'):
        deadline = time.monotonic() + 150
        while state() != {'phase': phase, 'state': 'ready'}:
            if time.monotonic() > deadline:
                raise TimeoutError('Waiting for ' + phase)
            time.sleep(.25)
        (args.output / (phase + '-before-memory.txt')).write_text(adb('dumpsys meminfo com.termux'))
        adb('dumpsys gfxinfo com.termux reset')
        # Capture stale ring records before starting so only new frame IDs are retained.
        previous = parse_frames(adb('dumpsys gfxinfo com.termux framestats'))
        cutoff = max(previous, default=0)
        touch(phase + '.go')
        frames = {}
        while True:
            raw = adb('dumpsys gfxinfo com.termux framestats')
            frames.update({k: v for k, v in parse_frames(raw).items() if k > cutoff})
            if state() == {'phase': phase, 'state': 'done'}:
                # Completion can race the preceding sample; collect the tail before ACK.
                raw = adb('dumpsys gfxinfo com.termux framestats')
                frames.update({k: v for k, v in parse_frames(raw).items() if k > cutoff})
                break
            if time.monotonic() > deadline:
                raise TimeoutError('Collecting ' + phase)
            time.sleep(.75)
        (args.output / (phase + '-gfxinfo.txt')).write_text(raw)
        (args.output / (phase + '-frames.json')).write_text(json.dumps(list(frames.values())))
        (args.output / (phase + '-after-memory.txt')).write_text(adb('dumpsys meminfo com.termux'))
        (args.output / (phase + '-thermal.txt')).write_text(adb('dumpsys thermalservice'))
        summary = {'phase': phase, 'sampled_frames': len(frames)}
        for label, begin, end in [('frame', 'IntendedVsync', 'FrameCompleted'),
                                  ('draw', 'DrawStart', 'SyncQueued'),
                                  ('ui', 'PerformTraversalsStart', 'SyncQueued'),
                                  ('gpu', 'SwapBuffers', 'GpuCompleted')]:
            durations = [(f[end]-f[begin])/1e6 for f in frames.values()
                         if end in f and begin in f and 0 <= f[end]-f[begin] < 1e9]
            summary[label + '_ms'] = {str(p): percentile(durations, p) for p in (.5, .9, .95, .99)}
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
        touch(phase + '.ack')
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            result = json.loads(app('cat ' + shlex.quote(args.remote_dir + '/result.json')))
            (args.output / 'workload.json').write_text(json.dumps(result, indent=2))
            break
        except (ValueError, subprocess.CalledProcessError):
            time.sleep(.2)
    else:
        raise TimeoutError('Waiting for valid workload result.json')
    (args.output / 'summary.json').write_text(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
