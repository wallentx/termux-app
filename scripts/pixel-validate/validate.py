#!/usr/bin/env python3
"""Read-only package checks, temporary-file smoke tests, and optional small benchmarks."""

import argparse
import ctypes
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import ssl
import statistics
import subprocess
import sys
import tempfile
import time
import zlib


# Linux arm64 UAPI arch/arm64/include/uapi/asm/hwcap.h. Detection is not kernel usage.
HWCAP = {"asimd": 1, "aes": 3, "sha2": 6, "crc32": 7, "asimdhp": 10,
         "sha3": 17, "asimddp": 20, "sha512": 21, "sve": 22, "asimdfhm": 23}
HWCAP2 = {"sve2": 1, "svei8mm": 9, "svebf16": 12, "i8mm": 13,
          "bf16": 14, "sme": 23, "sme2": 37}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, UnicodeError):
        return None


def run(command, cwd=None, timeout=10):
    """Bound execution time/output; terminate the process group on timeout."""
    started = time.perf_counter()
    with tempfile.TemporaryFile() as output:
        try:
            child = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as error:
            return {"status": "FAIL", "detail": str(error), "seconds": time.perf_counter() - started}
        try:
            code = child.wait(timeout=timeout)
            status = "PASS" if code == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            status, code = "FAIL", None
        output.seek(0)
        detail = output.read(4096).decode("utf-8", "replace").strip()
        if code is None:
            detail = "Timed out after %ss; process group killed. " % timeout + detail
    return {"status": status, "exit_code": code, "detail": detail,
            "seconds": round(time.perf_counter() - started, 6)}


def cpu_capabilities():
    if platform.machine().lower() not in ("aarch64", "arm64"):
        return {"status": "SKIP", "detail": "The HWCAP decoder supports ARM64 only"}
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.getauxval.argtypes = [ctypes.c_ulong]
        libc.getauxval.restype = ctypes.c_ulong
        values = []
        for key in (16, 26):  # AT_HWCAP, AT_HWCAP2
            ctypes.set_errno(0)
            value = libc.getauxval(key)
            error = ctypes.get_errno()
            if error:
                raise OSError(error, os.strerror(error))
            values.append(value)
        features = {name: bool(values[0] & (1 << bit)) for name, bit in HWCAP.items()}
        features.update({name: bool(values[1] & (1 << bit)) for name, bit in HWCAP2.items()})
        vectors = {}
        libc.prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
        libc.prctl.restype = ctypes.c_int
        for name, operation in (("sve", 51), ("sme", 64)):
            if not features[name]:
                vectors[name] = {"status": "SKIP", "detail": "Not advertised by HWCAP"}
                continue
            ctypes.set_errno(0)
            value = libc.prctl(operation, 0, 0, 0, 0)
            error = ctypes.get_errno()
            vectors[name] = {"status": "PASS" if value >= 0 else "UNKNOWN",
                             "vector_length_bytes": value & 0xffff if value >= 0 else None,
                             "errno": error if value < 0 else 0}
        return {"status": "PASS", "source": "getauxval in this Python process",
                "hwcap": hex(values[0]), "hwcap2": hex(values[1]), "features": features,
                "thread_vector_lengths": vectors,
                "note": "Availability only; no optional SIMD instructions are executed or benchmarked."}
    except (AttributeError, OSError) as error:
        return {"status": "UNKNOWN", "detail": str(error)}


def power_snapshot():
    base = Path("/sys/class/power_supply/battery")
    return {name: read_text(base / name) for name in ("capacity", "temp", "status")}


def metadata():
    properties = {}
    for name in ("ro.product.model", "ro.soc.model", "ro.build.version.release",
                 "ro.build.version.sdk", "ro.build.version.sdk_full"):
        result = run(["/system/bin/getprop", name])
        properties[name] = result["detail"] if result["status"] == "PASS" else None
    env_names = ("TERMUX_VERSION", "TERMUX_APP__VERSION_NAME", "TERMUX_APP__TARGET_SDK",
                 "TERMUX_APP__PACKAGE_MANAGER", "TERMUX_APP_PACKAGE_MANAGER")
    return {"android": properties, "termux_environment": {k: os.environ.get(k) for k in env_names},
            "architecture": platform.machine(), "uid": os.getuid(), "python": platform.python_version(),
            "openssl": ssl.OPENSSL_VERSION, "page_size": os.sysconf("SC_PAGESIZE"),
            "selinux_context": read_text("/proc/self/attr/current"),
            "preload_configured": bool(os.environ.get("LD_PRELOAD")),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def smoke_tests(directory):
    checks = []

    def check(name, command, expected=None):
        executable = shutil.which(command[0])
        if not executable:
            result = {"status": "SKIP", "detail": command[0] + " is not installed"}
        else:
            result = run([executable, *command[1:]], cwd=directory)
            if result["status"] == "PASS" and expected is not None and result["detail"] != expected:
                result.update(status="FAIL", detail="Unexpected output: " + result["detail"])
        checks.append(dict(name=name, **result))

    check("shell child process and pipe", ["sh", "-c", "printf termux-ok | cat"], "termux-ok")
    check("Python child process", [sys.executable, "-c",
          "import subprocess; print(subprocess.check_output(['sh','-c','printf python-child-ok']).decode())"],
          "python-child-ok")
    # Exercise executable scripts, including a shebang with an argument and a path with spaces.
    shell = shutil.which("sh")
    if shell:
        script = directory / "script with spaces"
        script.write_text("#!%s -e\nprintf '%%s' \"$1\"\n" % shell)
        script.chmod(0o700)
        check("private shebang execution", [str(script), "argument with spaces"], "argument with spaces")
    else:
        checks.append({"name": "private shebang execution", "status": "SKIP", "detail": "sh is not installed"})
    for runtime in ("node", "bun"):
        check(runtime + " child process", [runtime, "-e",
              "process.stdout.write(require('child_process').execFileSync('sh',['-c','printf js-child-ok']))"],
              "js-child-ok")
    for tool, flag in (("git", "--version"), ("ssh", "-V"), ("tmux", "-V"),
                       ("gh", "--version"), ("go", "version"), ("npm", "--version"),
                       ("codex", "--version"), ("claude", "--version"), ("opencode", "--version")):
        check(tool + " startup", [tool, flag])
    check("Pacman local database", ["pacman", "-Q", "bash", "termux-exec"])
    try:
        original = directory / "file"
        renamed = directory / "renamed"
        link = directory / "link"
        original.write_bytes(b"termux-storage-check\0\xff")
        original.rename(renamed)
        link.symlink_to(renamed.name)
        if link.read_bytes() != b"termux-storage-check\0\xff":
            raise OSError("Readback did not match")
        checks.append({"name": "private storage write/rename/symlink", "status": "PASS"})
    except OSError as error:
        checks.append({"name": "private storage write/rename/symlink", "status": "FAIL", "detail": str(error)})
    return checks


def benchmarks(directory):
    data = bytes(range(256)) * 32768  # Fixed synthetic 8 MiB input; no external downloads.
    results = []

    def measure(name, operation, byte_count=None):
        samples = []
        try:
            operation()  # Warm-up, with the same correctness check as measured iterations.
            for _ in range(3):
                start = time.perf_counter()
                operation()
                samples.append(time.perf_counter() - start)
            median = statistics.median(samples)
            result = {"name": name, "status": "PASS", "seconds": samples, "median_seconds": median}
            if byte_count:
                result["MiB_per_second"] = byte_count / (1024 * 1024) / median
            results.append(result)
        except (OSError, RuntimeError) as error:
            results.append({"name": name, "status": "FAIL", "detail": str(error)})

    expected = hashlib.sha256(data).digest()

    def digest():
        for _ in range(8):
            if hashlib.sha256(data).digest() != expected:
                raise RuntimeError("SHA-256 output mismatch")

    def compression():
        if zlib.decompress(zlib.compress(data, 6)) != data:
            raise RuntimeError("Compression round trip failed")

    def storage():
        path = directory / "benchmark.bin"
        with path.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.read_bytes() != data:
            raise RuntimeError("Storage readback mismatch")

    def spawn():
        for _ in range(10):
            result = run(["sh", "-c", "printf ok"], cwd=directory)
            if result["status"] != "PASS" or result["detail"] != "ok":
                raise RuntimeError("Child-process benchmark failed: " + result["detail"])

    measure("sha256_64MiB", digest, len(data) * 8)
    measure("zlib_level6_8MiB_roundtrip", compression, len(data))
    measure("private_storage_8MiB_fsync_readback", storage, len(data))
    measure("ten_shell_children", spawn)
    return results


MANUAL = [
    "Long-press a word: Copy/Paste/More appears without touching a selection handle; repeat after dragging handles.",
    "Copy, paste, and More work; cancel selection, rotate, reopen keyboard, and repeat near the bottom row.",
    "Open a second session; switch apps and return; verify both sessions and the notification remain usable.",
    "Check shared-storage access and LAN SSH using your chosen files and host; no network probes run automatically.",
    "Review package installation/update, sixel rendering, and your usual agent workflows separately; startup checks do not prove these.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bench", action="store_true", help="also run four small, fixed-workload benchmarks")
    parser.add_argument("--output", type=Path, help="new JSON report path (existing files are never overwritten)")
    args = parser.parse_args(argv)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = args.output or Path.home() / ("termux-validation-" + stamp + ".json")
    # Reserve the output before running tests; no overwrite, and mode 0600 for diagnostic metadata.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        report = {"schema_version": 1, "timestamp_utc": stamp, "metadata": metadata(),
                  "capabilities": cpu_capabilities(), "power_before": power_snapshot(),
                  "manual_checks": [{"status": "NOT_RUN", "instruction": item} for item in MANUAL],
                  "limitations": ["Run inside the installed Termux app, not adb shell or a VM.",
                                  "No packages are installed/updated and no remote hosts are contacted by this runner.",
                                  "Benchmarks use installed Python/OpenSSL/zlib; they do not identify selected SIMD kernels.",
                                  "Storage results include page cache and Python overhead; they are not raw flash bandwidth.",
                                  "UID/SELinux describe this process; target SDK is reported from Termux's environment."]}
        temp_base = os.environ.get("TMPDIR") or str(Path.home())
        with tempfile.TemporaryDirectory(prefix="termux-validation-", dir=temp_base) as temporary:
            directory = Path(temporary)
            report["checks"] = smoke_tests(directory)
            report["benchmarks"] = benchmarks(directory) if args.bench else []
        report["power_after"] = power_snapshot()
        report["summary"] = {status: sum(item["status"] == status for item in report["checks"] + report["benchmarks"])
                             for status in ("PASS", "FAIL", "SKIP")}
        json.dump(report, stream, indent=2)
        stream.write("\n")
    for item in report["checks"] + report["benchmarks"]:
        print("%-4s %s" % (item["status"], item["name"]))
    print("\nCapabilities: " + report["capabilities"]["status"] + " (availability, not measured acceleration)")
    print("Report: " + str(output.resolve()))
    print("Manual check: " + MANUAL[0])
    return 1 if report["summary"]["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
