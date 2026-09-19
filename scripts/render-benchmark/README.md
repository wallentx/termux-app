# Installed-app rendering measurement

No build required. `workload.py` runs in a foreground Termux terminal; `capture.py`
runs on an ADB-connected host using Python 3. The installed APK must allow
`run-as com.termux` (the fork's debug APK does).

1. Copy `workload.py` into the Pixel's Termux home.
2. On the host, start the collector with fresh output and remote directories:
   ```sh
   python scripts/render-benchmark/capture.py --serial IP:PORT \
     --remote-dir /data/data/com.termux/files/home/render-run-1 \
     --output "$HOME/reports/render-run-1"
   ```
3. Within 120 seconds, run in the Pixel's visible Termux terminal:
   ```sh
   python ~/workload.py ~/render-run-1
   ```

Default workload: three 20-second phases paced at 60 updates/second: colored text
scrolling, redraws of a pre-existing 960x600 sixel image, and replacement of that
image without declared raster dimensions (includes bitmap growth/decoding).
Use `--seconds 5` for a shorter probe; `--fps 30` reduces load. Keep the window,
font size, keyboard, other apps, and power conditions consistent between runs.

The alternate screen protects existing terminal contents and is restored on normal
exit or Ctrl-C. Each run requires a new remote directory to prevent stale signals.
The collector does not install APKs, change device settings, or stop applications.

`summary.json` includes sampled frame, UI traversal, draw, and GPU-completion
interval percentiles. Draw time covers the activity's draw stage, not exclusively
TerminalRenderer. Raw `gfxinfo` retains Android's aggregate frame/deadline counters;
its histogram is bucketed, whereas percentiles in the summary use frame timestamps.
Frame samples are collected repeatedly to avoid losing the circular buffer. They
exclude flagged frames and may differ slightly in count from aggregate counters.
GPU-completion intervals are wall-clock intervals, not isolated GPU execution time.
`workload.json` records terminal size, producer updates, and late producer deadlines.
Produced updates are not guaranteed to become distinct displayed frames.

Memory snapshots are process PSS/heap snapshots, not peak-memory or allocation
profiles. Thermal state is saved after each phase. Wireless ADB, background apps,
JIT compilation, refresh rate and CPU/GPU frequency add noise: repeat comparisons
and do not interpret these numbers as a universal FPS or SIMD speedup.

On older builds, rapid image replacement can retain gigabytes until the periodic
image sweep. Start with a shorter run when testing such builds.
