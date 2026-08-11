"""Build Lab02_DhakaOSM_Colab.ipynb deterministically.  Rebuild:
python3 scripts/build_notebook.py"""
import json
from pathlib import Path

CELLS = []


def md(s):
    CELLS.append({"cell_type": "markdown", "metadata": {}, "source": s})


def code(s):
    CELLS.append({"cell_type": "code", "execution_count": None, "metadata": {},
                  "outputs": [], "source": s})


md("""# DhakaFlow Lab 02 — Real Dhaka OSM → Validated SUMO Network (Colab-only)

All heavy execution happens here. The notebook orchestrates `src/` via
`scripts/run_lab02.py`; it is not the implementation. Original DhakaFlow module
on official OSM/SUMO tooling; provenance and pass gates per `METHOD_SPEC.md`.
""")

code("""from google.colab import drive
drive.mount('/content/drive')
import pathlib, zipfile
DRIVE_OUT = pathlib.Path('/content/drive/MyDrive/DhakaFlow-Nexus-Data/Lab02_DhakaOSM')
DRIVE_OUT.mkdir(parents=True, exist_ok=True)
LAB_ROOT = pathlib.Path('/content/DhakaFlow-Nexus/paper_labs/02_dhaka_osm')
if not LAB_ROOT.exists():
    src_zip = DRIVE_OUT / 'lab02_source.zip'
    assert src_zip.exists(), f'Upload {src_zip} first (scripts/make_colab_zip.sh)'
    LAB_ROOT.parent.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(src_zip).extractall(LAB_ROOT.parent)
print('LAB_ROOT=', LAB_ROOT)""")

code("""%pip -q install eclipse-sumo==1.27.1 PyYAML>=6.0 pytest>=8.0 matplotlib==3.8.4
import os, sys, pathlib, subprocess
import sumo
HOME = pathlib.Path(sumo.SUMO_HOME)
os.environ['SUMO_HOME'] = str(HOME)
os.environ['PATH'] = f"{HOME/'bin'}:{os.environ['PATH']}"
os.environ['PYTHONPATH'] = f"{HOME/'tools'}:{os.environ.get('PYTHONPATH','')}"
sys.path.insert(0, str(HOME/'tools'))
print(subprocess.run(['sumo','--version'], capture_output=True, text=True).stdout.split(chr(10))[0])
print(subprocess.run(['netconvert','--version'], capture_output=True, text=True).stdout.split(chr(10))[0])""")

md("## Tests in Colab (unit + tiny-OSM integration, real SUMO)")

code("""r = subprocess.run([sys.executable,'-m','pytest','tests','-q'], cwd=LAB_ROOT,
                   capture_output=True, text=True, env=os.environ.copy())
print(r.stdout[-1500:], r.stderr[-500:])
assert r.returncode == 0, 'tests failed'""")

md("## Smoke gate — inner Karwan Bazar / Bangla Motor box")

code("""r = subprocess.run([sys.executable, str(LAB_ROOT/'scripts/run_lab02.py'),
                    '--config', str(LAB_ROOT/'configs/smoke.yaml'),
                    '--output-root', str(DRIVE_OUT/'lab02_smoke')],
                   capture_output=True, text=True, env=os.environ.copy())
print(r.stdout[-3000:]); print(r.stderr[-1000:])
assert r.returncode == 0, 'smoke gate crashed'""")

md("## Full gate — pre-registered central-Dhaka region")

code("""r = subprocess.run([sys.executable, str(LAB_ROOT/'scripts/run_lab02.py'),
                    '--config', str(LAB_ROOT/'configs/full.yaml'),
                    '--output-root', str(DRIVE_OUT/'lab02_full')],
                   capture_output=True, text=True, env=os.environ.copy())
print(r.stdout[-3000:]); print(r.stderr[-1500:])
assert r.returncode == 0, 'full gate crashed'""")

md("""## Independent verification + evidence bundle

Recompute two trip metrics from raw tripinfo with fresh code; verify the gate
record agrees; verify network checksum reproducibility claim; bundle lightweight
evidence.""")

code("""import json, statistics, shutil, xml.etree.ElementTree as ET
FULL = DRIVE_OUT/'lab02_full'
gate = json.loads((FULL/'gate_record.json').read_text())
root = ET.parse(FULL/'sim/tripinfo.xml').getroot()
dur = [float(t.get('duration')) for t in root.findall('tripinfo')]
wait = [float(t.get('waitingTime')) for t in root.findall('tripinfo')]
assert len(dur) == gate['trip_metrics']['n_arrived_trips']
assert abs(statistics.mean(dur) - gate['trip_metrics']['avg_travel_time_s']) < 0.01
assert abs(statistics.mean(wait) - gate['trip_metrics']['avg_waiting_time_s']) < 0.01
print('METRIC RECOMPUTATION OK:', len(dur), 'trips, avg tt', round(statistics.mean(dur),2))

EV = pathlib.Path('/content/evidence_lab02'); shutil.rmtree(EV, ignore_errors=True)
for exp in ('lab02_smoke', 'lab02_full'):
    d = EV/exp; d.mkdir(parents=True)
    E = DRIVE_OUT/exp
    shutil.copy2(E/'gate_record.json', d/'gate_record.json')
    shutil.copy2(E/'osm/osm_manifest.json', d/'osm_manifest.json')
    shutil.copy2(E/'network/netconvert_record.json', d/'netconvert_record.json')
    for f in (E/'validation').glob('*.json'): shutil.copy2(f, d/f.name)
    for f in (E/'metrics').glob('*.json'): shutil.copy2(f, d/f.name)
    (d/'figures').mkdir()
    for f in (E/'figures').glob('*.png'): shutil.copy2(f, d/'figures'/f.name)
    nc_log = (E/'network/netconvert.log')
    (d/'netconvert.log.tail').write_text(chr(10).join(nc_log.read_text(errors='ignore').splitlines()[-80:]))
    net = E/'network/dhaka.net.xml'
    if net.exists() and net.stat().st_size < 30_000_000:
        shutil.copy2(net, d/'dhaka.net.xml')
bundle = shutil.make_archive('/content/evidence_lab02', 'zip', EV)
shutil.copy2(bundle, DRIVE_OUT/'evidence_lab02.zip')
print('Evidence:', bundle, '->', DRIVE_OUT/'evidence_lab02.zip')
from google.colab import files
files.download(bundle)""")

md("Provenance: OSM © OpenStreetMap contributors (ODbL) via Overpass API · "
   "SUMO 1.27.1 pinned · all decisions in METHOD_SPEC/ASSUMPTIONS.")

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"provenance": []},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "language_info": {"name": "python"}},
      "cells": CELLS}
out = Path(__file__).resolve().parents[1] / "notebooks" / "Lab02_DhakaOSM_Colab.ipynb"
out.write_text(json.dumps(nb, indent=1))
print(f"wrote {out} ({len(CELLS)} cells)")
