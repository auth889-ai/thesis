#!/bin/bash
# Veins 5.3.1 (Sommer, German, Dressler, IEEE TMC 2011; GPL-2.0, COPYING in the tree), pinned by its tag's commit, into
# ~/.dhakaflow/upstream/veins; built against OMNeT++ 6.2.0 (third_party/omnetpp/fetch.sh) as its README says: ./configure && make.
set -euo pipefail
COMMIT=6571085f9879003d03e804f8cee074843a9a3953
DEST=$HOME/.dhakaflow/upstream/veins
OPP=$HOME/.dhakaflow/upstream/omnetpp-6.2.0
if [ ! -d "$DEST/.git" ]; then git clone --quiet https://github.com/sommer/veins.git "$DEST"; fi
cd "$DEST"; git fetch --quiet --tags; git checkout --quiet "$COMMIT"
[ "$(git rev-parse HEAD)" = "$COMMIT" ] || { echo "commit mismatch"; exit 1; }
[ "${1:-}" = "--fetch-only" ] && { echo "fetched: $DEST at $COMMIT"; exit 0; }
set +u; pushd "$OPP" >/dev/null; source setenv -q; popd >/dev/null; set -u
./configure && make -j8 MODE=release
echo "built: $DEST at $COMMIT"
