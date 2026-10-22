#!/bin/sh
# Strata Asofwar (the fork) - Linux installer.
# Usage:
#     curl -fsSL https://github.com/Asofwar/Strata/releases/latest/download/install.sh | sh
# What it does: finds the fork's latest release on GitHub, downloads that release's source, unpacks it into
# ~/Strata-Asofwar/<version> and starts ./setup.sh, which builds the engine from source (CUDA toolkit needed) and asks
# which model to set up. The fork has not tested Linux; Windows has a ready engine in the release.
# Options (environment variables, all optional):
#     STRATA_VERSION=v1.0.0            a given release instead of the latest
#     STRATA_HOME=/opt/strata          where to unpack
#     STRATA_SETUP_ARGS="--setup --family cyber-tiel"   arguments for setup.sh
#     STRATA_NO_START=1                unpack only, do not start setup
set -eu

REPO="Asofwar/Strata"
die() { echo "strata-asofwar installer: $*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || die "curl is needed."
command -v tar >/dev/null 2>&1 || die "tar is needed."
[ "$(uname -s)" = "Linux" ] || die "this is the Linux installer; on Windows use install.ps1."

echo "Strata Asofwar installer"
if [ -n "${STRATA_VERSION:-}" ]; then
  tag="$STRATA_VERSION"
else
  tag=$(curl -fsSL -H "User-Agent: strata-asofwar-installer" "https://api.github.com/repos/$REPO/releases/latest" \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1) || true
  [ -n "$tag" ] || die "could not read the latest release of $REPO. Check your internet connection."
fi
version="${tag#v}"
home_dir="${STRATA_HOME:-$HOME/Strata-Asofwar}"
dest="$home_dir/$version"
echo "  Release: $tag"

if [ -x "$dest/setup.sh" ]; then
  echo "  $tag is already unpacked in $dest"
else
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  echo "Downloading..."
  curl -fsSL "https://github.com/$REPO/archive/refs/tags/$tag.tar.gz" -o "$work/src.tar.gz" \
    || die "the download failed. Check your internet connection and run this again; nothing was installed."
  mkdir -p "$work/unpack"
  tar -xzf "$work/src.tar.gz" -C "$work/unpack" || die "the archive could not be unpacked (is the disk full?)."
  inner=$(find "$work/unpack" -mindepth 1 -maxdepth 1 -type d | head -n 1)
  [ -n "$inner" ] && [ -f "$inner/setup.sh" ] || die "the archive does not look like a Strata Asofwar release."
  mkdir -p "$home_dir"
  mv "$inner" "$dest"
  chmod +x "$dest/setup.sh" 2>/dev/null || true
  echo "  Unpacked to $dest"
fi

if [ "${STRATA_NO_START:-}" = "1" ]; then
  echo "Done. To set up a model: cd $dest && ./setup.sh"
  exit 0
fi
echo "Starting setup (./setup.sh). For the fork's long-context models: ./setup.sh --setup --family cyber-tiel"
cd "$dest"
# setup asks questions: read them from the terminal, not from the pipe this script came through
if [ -r /dev/tty ]; then
  # shellcheck disable=SC2086
  exec ./setup.sh ${STRATA_SETUP_ARGS:-} </dev/tty
else
  # shellcheck disable=SC2086
  exec ./setup.sh ${STRATA_SETUP_ARGS:-}
fi
