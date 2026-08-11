from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]

def test_four_connections_and_tls_states():
    c=ET.parse(ROOT/'scenarios/unit_validation/connections.con.xml').getroot()
    assert len(c.findall('connection'))==4
    t=ET.parse(ROOT/'scenarios/unit_validation/tls.tll.xml').getroot().find('tlLogic')
    states=[p.attrib['state'] for p in t.findall('phase')]
    assert states==['GGrr','yyrr','rrGG','rryy']
