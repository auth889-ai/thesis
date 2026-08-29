from __future__ import annotations
from pathlib import Path
import argparse, subprocess


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dest', required=True)
    args=ap.parse_args()
    dest=Path(args.dest)
    repo=dest/'sumo-scenarios'
    if not repo.exists():
        subprocess.run(['git','clone','--depth','1','--filter=blob:none','--sparse',
                        'https://github.com/DLR-TS/sumo-scenarios.git',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'sparse-checkout','set','bologna/acosta'],check=True)
    sha=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    print('repo=',repo)
    print('commit=',sha)
    print('scenario=',repo/'bologna/acosta')

if __name__=='__main__': main()
