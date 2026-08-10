from pathlib import Path
import sys
import tempfile

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))
from src.metrics import parse_tripinfo, parse_queue_csv


def test_tripinfo_parser():
    xml='''<tripinfos>
      <tripinfo id="a" duration="10" waitingTime="2" timeLoss="3"/>
      <tripinfo id="b" duration="20" waitingTime="4" timeLoss="5"/>
    </tripinfos>'''
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'trip.xml'; p.write_text(xml)
        m=parse_tripinfo(p)
        assert m['completed_trips']==2
        assert m['mean_trip_duration_s']==15
        assert m['mean_waiting_time_s']==3


def test_queue_parser():
    csv='time,phase,ns_in_queue,ew_in_queue,ns_pressure,ew_pressure,vehicles\n0,0,2,3,0,0,5\n1,0,4,1,0,0,5\n'
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'q.csv'; p.write_text(csv)
        m=parse_queue_csv(p)
        assert m['mean_total_queue']==5
        assert m['max_total_queue']==5
