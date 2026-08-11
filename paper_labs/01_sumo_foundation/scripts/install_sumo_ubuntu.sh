#!/usr/bin/env bash
# FALLBACK ONLY. The Lab 01 Colab notebook uses scripts/install_colab.sh and
# eclipse-sumo==1.27.1 for a pinned runtime. Do not run this on the user's Mac.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq software-properties-common git >/dev/null
add-apt-repository -y ppa:sumo/stable
apt-get update -qq
apt-get install -y -qq sumo sumo-tools sumo-doc >/dev/null
sumo --version
netconvert --version
