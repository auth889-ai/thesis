from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from dhakaflow_lab01.demand import DemandPeriod, generate_route_file

def test_seed_reproducibility(tmp_path):
    periods=[DemandPeriod(0,100,360,180)]
    a=tmp_path/'a.xml'; b=tmp_path/'b.xml'; c=tmp_path/'c.xml'
    generate_route_file(a,123,periods); generate_route_file(b,123,periods); generate_route_file(c,124,periods)
    assert a.read_bytes()==b.read_bytes()
    assert a.read_bytes()!=c.read_bytes()
