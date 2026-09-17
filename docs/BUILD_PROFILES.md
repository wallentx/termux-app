# APK build profiles

The default `pixel11` profile produces one ARM64 APK per requested build type,
using the `pacman-android-7` bootstrap. It builds only ARM64 native libraries and
downloads only the ARM64 bootstrap. The other architectures and the older
bootstrap remain available through explicit options.

`pacman-android-7` means Pacman-based packages for Android 7 and newer (API 24+).
It is the bootstrap's compatibility baseline, not the application's target SDK.
The regular APK now targets API 37 and compiles against SDK 37.2. The diagnostic
uses the same target, adds probes, and requires Android 17. The normal minimum
SDK remains 21 to retain the older build options; the selected Pacman bootstrap
requires Android 7+. The target is configured, but Pixel runtime validation is
still required before treating this as a daily-use release.

Run Gradle builds only in CI or on another build host, not this Termux workspace.

| Selection | Option | APK output |
| --- | --- | --- |
| Default Pixel 11 build | `:app:assembleDebug` | One `*_arm64-v8a.apk` |
| All architectures | `:app:assembleDebug -PtermuxBuildProfile=all` | Four ABI APKs plus universal, using the existing debug split defaults |
| APT bootstrap | Set `TERMUX_PACKAGE_VARIANT=apt-android-7` | Selected profile with the retained APT bootstrap |
| Older bootstrap | Set `TERMUX_PACKAGE_VARIANT=apt-android-5` | Selected profile with Android 5/6-compatible bootstrap |
| SDK/SIMD diagnostic | `:app:assembleDebug -PpixelProbe=true` | One ARM64 diagnostic APK, with target SDK 37 |

For a single release APK, use `:app:assembleRelease`; the default profile still
selects ARM64. Signing remains a separate release configuration. Switching build
profiles in an existing checkout can leave old outputs in the output directory;
use a clean build on the build host when comparing the artifact set.

## GitHub Actions

Normal push/PR builds and published-release attachment jobs default to one
`pacman-android-7` ARM64 APK, plus checksum and metadata files.

- For one manual full build, run **Build** with `all_apks` enabled.
- To restore full automatic builds and release attachments, set the repository
  Actions variable `TERMUX_BUILD_ALL_APKS` to the string `true`. This enables both
  APT bootstrap variants as well as Pacman, for every architecture. Unset it to
  restore the single APK.
- **Pixel SDK and SIMD probe** is manual-only. It will not add a second APK to
  normal push/PR builds.

The Pixel profile chooses the device's architecture and avoids unused payloads.
It does not claim measured SIMD acceleration or change CPU instruction tuning. See
[the feature plan](PIXEL11_FEATURE_PLAN.md) for those separate validation gates.

## Pacman bootstrap

The fork pins Termux-Pacman's
[2026.09.13-r1 bootstrap](https://github.com/termux-pacman/termux-packages/releases/tag/bootstrap-2026.09.13-r1%2Bpacman.android-7)
and SHA-256 checksums for all four architectures. Builds verify the selected ZIP's
checksum before embedding it. The ARM64 archive was downloaded and its checksum
verified during integration; no code from it was executed locally.

This gives our APK a Pacman default using the maintained Android/Termux package
feed. We do not yet build or host our own entire package repository. These packages
are built for Termux's Android runtime and private prefix, not a stock Arch Linux
root filesystem. A future fork-owned package feed can be layered on separately.

The archive contains `pacman`, its package database, repository configuration,
keyring material, and a profile script that invokes bootstrap second-stage setup
on first login. Runtime completion of that setup, repository synchronization and
package installation still need testing on the Pixel. Preserve the archive's
signature settings and keyring setup when customizing it.

The new default applies to fresh environments. Installing an APK does not convert
an existing APT prefix. The Pacman build detects an APT-only database and exits
with migration instructions, without invoking the bootstrap reset/retry path.
An APT build remains available for using the existing environment. No installed
Termux environment was modified while implementing these defaults.

## API 37 runtime migration

Normal Termux launches on Android 10+ with target SDK 29+ route app-private dynamic
executables through the system linker. Script interpreters and shebang arguments
are resolved first; login shells retain login behavior. The modern termux-exec
linker preload is installed in the environment before the first shell so child
processes can use the same mechanism. Failsafe sessions retain the system shell.
The installer atomically replaces the packaged direct preload with its matching
linker variant, because `login` resets `LD_PRELOAD`; custom preload contents are
left untouched. This applies to fresh Pacman installs and existing modern prefixes.

The services declare `specialUse`, notification intents are immutable, and the
activity receiver is restricted to the app/shared UID. The app requests notification
and Android 17 local-network permissions once. If denied, grant them later in
Android Settings > Apps > Termux > Permissions. The existing all-files-access flow
remains available through `termux-setup-storage`.

Static binaries, raw exec syscalls, `/proc/self/exe`, plugin/background launches,
keyboard/insets, package installation and upgrades still require device tests.
The older APT bootstraps may lack modern termux-exec; use the explicit
`-PtargetSdkVersion=28` override for those legacy environments. No local builds
or device installations were performed for this change.
