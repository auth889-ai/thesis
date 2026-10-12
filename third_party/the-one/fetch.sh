#!/bin/bash
# The ONE 1.6.0 (Keranen, Ott, Karkkainen, SIMUTools 2009; GPL-3.0, LICENSE.txt in the tree), pinned by its git commit, into
# ~/.dhakaflow/upstream/the-one, compiled as its compile.bat does (javac).
set -euo pipefail
COMMIT=42b6e20f45799f2533866df215768fa9aedd0f4f
DEST=$HOME/.dhakaflow/upstream/the-one
if [ ! -d "$DEST/.git" ]; then git clone --quiet https://github.com/akeranen/the-one.git "$DEST"; fi
cd "$DEST"; git fetch --quiet --tags; git checkout --quiet "$COMMIT"
[ "$(git rev-parse HEAD)" = "$COMMIT" ] || { echo "commit mismatch"; exit 1; }
# compile.bat's eight javac lines, unchanged except -extdirs lib/ (removed from javac in JDK 9) -> -cp .:lib/*
for d in core movement report routing gui input applications interfaces; do javac -nowarn -cp ".:lib/*" $d/*.java; done
echo "built: $DEST at $COMMIT"
