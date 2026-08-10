from pathlib import Path
import xml.etree.ElementTree as ET

LAB = Path(__file__).resolve().parents[1]
SC = LAB / 'scenarios' / 'unit_intersection'


def test_tls_has_safe_transitions():
    root = ET.parse(SC / 'tls.add.xml').getroot()
    phases = root.find('tlLogic').findall('phase')
    states = [p.attrib['state'] for p in phases]
    assert states == ['GGrr', 'yyrr', 'rrrr', 'rrGG', 'rryy', 'rrrr']
    assert all(len(s) == 4 for s in states)
    # No direct conflicting all-green state exists.
    assert 'GGGG' not in states


def test_routes_are_deterministic_period_flows():
    root = ET.parse(SC / 'routes.rou.xml').getroot()
    flows = root.findall('flow')
    assert len(flows) == 4
    assert all('period' in f.attrib for f in flows)
    assert all('probability' not in f.attrib for f in flows)


def test_network_source_has_one_tls():
    root = ET.parse(SC / 'nodes.nod.xml').getroot()
    tls = [n for n in root.findall('node') if n.attrib.get('type') == 'traffic_light']
    assert [n.attrib['id'] for n in tls] == ['J0']
