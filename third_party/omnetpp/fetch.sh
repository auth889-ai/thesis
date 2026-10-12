#!/bin/bash
# OMNeT++ 6.2.0 for macOS arm64, the official release (Academic Public License, see LICENSE in the tree), into ~/.dhakaflow/upstream.
# Pinned by the sha256 GitHub publishes for the asset; refused on mismatch. Then configure + build as in its install guide.
set -euo pipefail
VER=6.2.0; ASSET=omnetpp-$VER-macos-aarch64.tgz
SHA=db8dd6cbb84bf3b9a78578aa61a1d1d1ec9a5e65579a6cd3561266d92cd7b695
URL=https://github.com/omnetpp/omnetpp/releases/download/omnetpp-$VER/$ASSET
DEST=$HOME/.dhakaflow/upstream; mkdir -p "$DEST"; cd "$DEST"
[ -f "$ASSET" ] || curl -fL --retry 3 -o "$ASSET" "$URL"
echo "$SHA  $ASSET" | shasum -a 256 -c -
[ -d omnetpp-$VER ] || tar xzf "$ASSET"
echo "unpacked: $DEST/omnetpp-$VER"
