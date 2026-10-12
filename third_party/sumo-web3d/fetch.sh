#!/bin/bash
# sumo-web3d (Sidewalk Labs, EPL-2.0, archived) at its last commit, into ~/.dhakaflow/upstream. Pinned by commit SHA; the tarball's
# sha256 is recorded on first fetch and checked after. Reference for streaming TraCI state to the browser (live twin).
set -euo pipefail
SHA=d89fe8014879153d30632996f35b68efb4d8c086
TGZ_SHA=${TGZ_SHA:-}
DEST=$HOME/.dhakaflow/upstream; mkdir -p "$DEST"; cd "$DEST"
ASSET=sumo-web3d-$SHA.tar.gz
[ -f "$ASSET" ] || curl -fL --retry 3 -o "$ASSET" "https://codeload.github.com/sidewalklabs/sumo-web3d/tar.gz/$SHA"
GOT=$(shasum -a 256 "$ASSET" | cut -d' ' -f1)
if [ -n "$TGZ_SHA" ] && [ "$GOT" != "$TGZ_SHA" ]; then echo "sha256 mismatch: $GOT"; exit 1; fi
echo "sha256 $GOT  $ASSET"
[ -d sumo-web3d-$SHA ] || tar xzf "$ASSET"
echo "unpacked: $DEST/sumo-web3d-$SHA"
