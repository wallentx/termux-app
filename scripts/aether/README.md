# Aether native glibc prototype

Build only in CI, using Build > aether_prototype=true. The default APK profile,
SDK 37, and existing rish installation remain available. This is an ARM64 proof
of direct app-UID execution, not a general Linux distribution or sandbox.

The prototype APK contains an executable glibc loader in Android's installed
native-library directory, matching Android-adapted glibc 2.44-0 libraries, and a
Bionic helper. `aether-run /absolute/path/to/linux-aarch64-program [arguments]`
uses the installed loader directly, bypassing the Bionic termux-exec interceptor.
The runtime is installed privately at `$HOME/../aether`; package-managed files
under `$PREFIX/glibc` are unchanged and supply optional dependencies such as
libgcc_s. No Geekbench binary is redistributed.

The glibc preload delegates getaddrinfo to a separate Bionic process, translating
flags and result/error structures. Android resolves these queries for Termux's
UID on its current default network. VPN/Private DNS policy is delegated to the
platform; a VPN transition has not yet been tested. The two libcs never coexist
in one process. File wrappers map `/etc/resolv.conf` to Termux's existing resolver
file and common certificate paths to its CA bundle. Programs with independent
DNS implementations can still use the static resolv.conf contents; they are not
claimed to use Android Private DNS. Reads of `/sys/class/dmi/id/sys_vendor` and
`/sys/class/dmi/id/product_name` map to private files populated from Android's
`Build.MANUFACTURER` and `Build.MODEL` at app startup. This lets Linux programs
report the real device make/model without inventing DMI serial numbers or
motherboard information. It does not change the system's sysfs or CPU features. Static binaries/direct syscalls are outside
this preload's coverage. Do not claim universal `/etc` virtualization.

The preload also makes readlink(/proc/self/exe) report the requested program,
so programs such as Geekbench locate sibling assets. execve, execv, and
posix_spawn of dynamic Linux/AArch64 ELF children are routed through the same
loader. PATH-searching exec functions, script interpreters, system(), arbitrary
Bionic subprocesses, and environments that remove the compatibility variables
are not yet covered. Existing syscall and filesystem constraints still apply.

`aether-probe` checks app UID, executable identity, resolv.conf visibility,
Android manufacturer/model files, Android-backed DNS success/failure/numeric cases, and execve/posix_spawn children.
Run it in a native Termux session, not ADB shell or run-as, to validate SDK-37
execution restrictions. Then validate Geekbench --sysinfo and a real HTTPS
client. A successful probe is not a benchmark or evidence of a performance gain.

## Runtime provenance and source

The binaries were copied from the Pixel's Pacman-installed glibc 2.44-0 package,
whose local package database records PGP validation. `provenance.json` pins every
included ELF SHA-256 and the package recipe revision. CI checks those hashes
before building. The APK retains the loader unstripped so its hash is preserved.

The prototype build MUST publish the accompanying aether-source artifact with
its APK: exact GNU glibc 2.44 source tarball, Termux package recipes/build scripts
at the recorded commit, compatibility sources, copyright/license notices, and
provenance. The prototype APK is not intended for publishing through ordinary
release workflows until equivalent source distribution is wired there.
The preload and launcher sources in this directory use the repository's license;
the glibc libraries retain their upstream licenses. See COPYING.LIB and LICENSES.
