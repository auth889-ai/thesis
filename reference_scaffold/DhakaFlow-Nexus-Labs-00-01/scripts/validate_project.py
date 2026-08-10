from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / '.env.example',
    ROOT / 'CLAUDE.md',
    ROOT / 'paper_labs/00_utd19/notebooks/Lab00_UTD19_Full_Colab.ipynb',
    ROOT / 'paper_labs/01_sumo_foundation/notebooks/Lab01_SUMO_Foundation_Colab.ipynb',
]
missing = [str(p) for p in REQUIRED if not p.exists()]
if missing:
    raise SystemExit('Missing required files:\n' + '\n'.join(missing))
print('Project structure: OK')
