#!/usr/bin/env bash
set -euo pipefail
out=$1
mkdir -p "$out"
curl --fail --location --retry 3 https://ftp.gnu.org/gnu/libc/glibc-2.44.tar.xz -o "$out/glibc-2.44.tar.xz"
printf '%s  %s\n' 37f600f2bef3c5e8300147059568b2a2e40a7ad6ccc65ce942556d49429cc667 "$out/glibc-2.44.tar.xz" | sha256sum --check
curl --fail --location --retry 3 \
  https://api.github.com/repos/termux-pacman/glibc-packages/tarball/c2b00b9e5c58d87f548b1793149d389f48bf9bc5 \
  -o "$out/termux-glibc-recipes-c2b00b9e.tar.gz"
cp app/src/aether/assets/aether/{COPYING.LIB,LICENSES,provenance.json} "$out/"
cp scripts/aether/{launcher.c,compat.c,probe.c,build.sh,source-bundle.sh,README.md} "$out/"
