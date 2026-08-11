from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from dhakaflow_lab01.metrics import percentile

def test_percentile_basic():
    assert percentile([1,2,3,4,5],50)==3
    assert percentile([1,2,3,4,5],100)==5
