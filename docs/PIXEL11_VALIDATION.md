# Validate the installed Termux fork

The user has installed the API 37 APK on the Pixel and reports that it works.
This establishes basic startup, not completion of every workload check below.

Run this script **inside that installed Termux app**, not through `adb shell`,
PRoot, SSH into another computer, or a VM. It needs Python 3 and uses only its
standard library. If Python is missing, install it using your package manager
before running the script; the script never installs anything itself.

From a checkout of this fork:

```sh
python3 scripts/pixel-validate/validate.py
python3 scripts/pixel-validate/validate.py --bench
```

Alternatively, download the single script and run it:

```sh
curl -fLo termux-validate.py https://raw.githubusercontent.com/wallentx/termux-app/dev/scripts/pixel-validate/validate.py
python3 termux-validate.py --bench
```

Normal checks typically take 5-30 seconds with healthy tools. Each child command
has a 10-second timeout; an installed but broken tool can lengthen the run.
Benchmarks normally add 5-30 seconds. They use three measured samples after a
warm-up. Child startup failures/timeouts can take longer.

## Reading the result

The script prints PASS/FAIL/SKIP and writes a new private
`~/termux-validation-<timestamp>.json`. Exit code 1 means at least one automated
check or benchmark failed. Existing report files are never overwritten. Set
`--output <new-path>` to choose the report location.

| Result | Meaning |
| --- | --- |
| PASS | The named operation completed successfully |
| FAIL | An installed command failed, timed out, or returned incorrect output |
| SKIP | An optional command is missing, or the probe does not apply |
| UNKNOWN | A capability query was unavailable or denied |
| NOT_RUN | A UI or external integration check still needs manual testing |

Checks cover private scripts with shebang arguments, shell pipelines, Python and
available Node/Bun child execution, tool startup, Pacman's local package database,
and private storage write/rename/symlink behavior. Version checks for Git/SSH/tmux
and agent tools establish startup only. The script doesn't install/update packages,
change settings, alter the clipboard, compile code, or contact remote hosts itself.
It executes installed tools' version commands; custom wrappers may have their own
side effects. Temporary files are scoped to a new directory under `$TMPDIR` (or
the private home directory if unset) and cleaned up on normal completion.

Metadata includes the app version/target SDK exported by Termux, OS/model, Python,
OpenSSL, process UID/SELinux context, page size, and readable battery sysfs values.
It does not dump all environment variables, credentials, serial numbers, or IMEI.
Review command output and paths in the report before sharing it.

## Benchmarks and SIMD

`--bench` measures SHA-256 throughput, a zlib compression/decompression round trip,
file write/fsync/readback, and ten shell launches. Input is fixed, synthetic, and
8 MiB in size. Hashing processes it eight times per sample. Storage numbers include
the page cache and Python overhead; they are not raw flash bandwidth. Compression
uses a highly compressible repeating input, not a representative file corpus.

ARM64 capability reporting uses `getauxval` and read-only SVE/SME `prctl` queries in
the Python process. Feature bits and vector lengths **do not prove that a benchmark
uses SVE2 or SME2**, or that it is faster than another build. No optional instructions
are issued by the capability probe. Inaccessible battery readings remain null;
SVE/SME query failures retain their errno instead of implying lack of hardware.

Compare reports using the same script hash, package versions, phone temperature,
power/charging state, and workload. Keep the app visible and avoid other heavy
work during comparison. A kernel-dispatch audit and sustained thermal benchmarks
remain separate work.

## Selection-menu regression check

1. Run `printf 'Select this word and copy it.\n'` and long-press a word. Copy/Paste/More
   should appear on the initial selection without touching a handle again.
2. Drag each handle. The menu should hide while moving and return after release.
3. Exercise Copy, Paste, and More; cancel selection and repeat on a single character.
4. Repeat near the bottom row, with the keyboard open/closed, and after rotation.
5. Switch sessions or leave the app while selection is active; no stale menu should reappear.

The regression tests cover scheduling, selection state, handle-release refresh,
single-cell bounds, finished modes and detached views using an Android test runtime.
The Android 17 path also resets the remote toolbar's hidden state before showing
it: a live Pixel check found the remote implementation could claim it was shown
and suppress identical requests while its window was still absent.
They do not reproduce Android 17's actual floating-toolbar implementation. Final
confirmation of the reported Android 17 symptom requires this device check.

Remaining manual checks are included in every JSON report: session persistence,
notification actions, shared storage, LAN SSH, package installation/update, sixel,
and normal agent workloads. AVF, the planned capability CLI, and other unimplemented
features are not counted as passing.
