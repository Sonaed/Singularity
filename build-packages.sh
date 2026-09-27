#!/bin/sh
# Construit les livrables sans modifier les sources de l'application.
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
version=2.0.0
stage="$root/packaging/debian"
dist="$root/dist"

mkdir -p "$dist" "$stage/usr/lib/singularity"
install -m 755 "$root/webready.py" "$stage/usr/lib/singularity/webready.py"
chmod 755 "$stage/usr/bin/singularity"

tar -C "$root" \
  --exclude='./dist' --exclude='./__pycache__' \
  -czf "$dist/Singularity-$version.tar.gz" \
  webready.py launch.sh build-packages.sh LICENSE packaging

if command -v dpkg-deb >/dev/null 2>&1; then
  dpkg-deb --build "$stage" "$dist/singularity-image-optimizer_${version}_all.deb"
else
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT HUP INT TERM
  printf '2.0\n' > "$work/debian-binary"
  tar -C "$stage/DEBIAN" -czf "$work/control.tar.gz" .
  tar -C "$stage" --exclude='./DEBIAN' -czf "$work/data.tar.gz" .
  ar rcs "$dist/singularity-image-optimizer_${version}_all.deb" \
    "$work/debian-binary" "$work/control.tar.gz" "$work/data.tar.gz"
fi

aur_stage=$(mktemp -d)
trap 'rm -rf "$aur_stage"' EXIT HUP INT TERM
mkdir -p "$aur_stage/singularity-image-optimizer-$version"
cp "$root/packaging/aur/PKGBUILD" "$root/packaging/aur/.SRCINFO" \
  "$root/packaging/aur/README.md" "$aur_stage/singularity-image-optimizer-$version/"
tar -C "$aur_stage" -czf "$dist/singularity-image-optimizer-aur-$version.tar.gz" \
  "singularity-image-optimizer-$version"

printf '%s\n' "Paquet Debian : $dist/singularity-image-optimizer_${version}_all.deb"
printf '%s\n' "Archive pour l'AUR : $dist/Singularity-$version.tar.gz"
printf '%s\n' "Bundle AUR local : $dist/singularity-image-optimizer-aur-$version.tar.gz"
