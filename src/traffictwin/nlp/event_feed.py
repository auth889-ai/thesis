#!/usr/bin/env python3
"""Text -> routing event: classify, geolocate against the Dhaka gazetteer, map to R1 edges, emit a slowdown.

    python -m traffictwin.nlp.event_feed --demo                          # 20 example posts -> results/nlp/events.jsonl
    python -m traffictwin.nlp.event_feed --text "Bus crash at Karwan Bazar, road blocked"
    python -m traffictwin.nlp.event_feed --file posts.txt                # one post per line
    python -m traffictwin.nlp.event_feed --to-weights results/nlp/weights_incident.xml \
        --base results/routing/static_s11_h900/edgedata.xml [--events results/nlp/events.jsonl]

Pipeline per post
  1. label, confidence   = results/nlp/tfidf_lr_dhaka_aug.joblib if present else tfidf_lr.joblib (predict_proba)
                           [--model distilbert uses results/nlp/distilbert/model]
  2. place, lat, lon     = longest gazetteer alias found on a word boundary (src/traffictwin/nlp/gazetteer.json)
  3. edges               = sumolib net.getNeighboringEdges(x, y, r=150 m) after net.convertLonLat2XY;
                           OUT_OF_NETWORK if the place is outside the R1 bounding box, NO_EDGE_IN_RADIUS
                           if inside but no edge within 150 m, NO_LOCATION if no gazetteer hit
  4. factor              = incident -> x10 (edges effectively blocked), congestion -> x3, irrelevant -> x1
Event JSON: {text, label, confidence, place, lat, lon, edges, factor, status, ...}

--to-weights rewrites a SUMO meanData table (the forecast / oracle weights the predictive arm consumes) with
traveltime multiplied by the event factor on every affected edge in every interval (edges absent from an
interval, e.g. excluded as empty, are added at free-flow x factor), so
    python -m traffictwin.digital_twin.runtime --arm predictive --weights <out.xml> ...
routes around the reported event.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
from traffictwin.paths import REPO
ROOT = HERE.parent
sys.path.insert(0, str(REPO))  # so `pipeline.*` resolves when run as a script
RESULTS = REPO / "results/nlp"
from traffictwin.digital_twin.network_file import DHAKA_R1, ensure_net  # noqa: E402

DEFAULT_NET = DHAKA_R1
GAZETTEER = HERE / "gazetteer.json"
LABELS = ["incident", "congestion", "irrelevant"]
FACTOR = {"incident": 10.0, "congestion": 3.0, "irrelevant": 1.0}
RADIUS_M = 150.0

DEMO_POSTS = [
    "Bus and CNG collision at Karwan Bazar signal, one lane blocked, police on the spot",
    "Heavy jam from Farmgate to Karwan Bazar, 40 minutes for 1 km",
    "Shahbagh intersection fully blocked by protesters, avoid the area",
    "Bangla Motor e ekta private car ulte gese, rasta bondho",
    "Slow moving traffic on Panthapath towards Science Lab",
    "Truck overturned on Bijoy Sarani, road blocked towards Jahangir Gate",
    "Kakrail to Moghbazar bumper to bumper as usual",
    "Malibagh rail crossing: train stuck, gates down for 30 min, cars piling up",
    "Best biryani near Kawran Bazar? Looking for suggestions",
    "Road cave-in at Dhanmondi 27, WASA digging, whole road closed",
    "New Market area e crazy jam, shopping rush",
    "Elephant Road closed for a political procession, police diverting traffic",
    "Gulistan flyover: motorcycle crash, two lanes blocked",
    "Motijheel office hours jam, Shapla Chattar theke Paltan porjonto",
    "Press Club er samne manob bondhon, rasta half block",
    "Hatirjheel link road: car fell into the drain, rescue ongoing, road closed",
    "Mohakhali flyover e bhoyonkor jam, ekdom norche na",
    "Cover van broke down on Tejgaon Satrasta, right lane closed",
    "Metro rail is the best thing that happened to Dhaka",
    "Accident near Sonargaon crossing, bus hit a divider, one lane shut",
]


# ----------------------------------------------------------------------------- classifier
class Classifier:
    def __init__(self, kind: str = "auto"):
        if kind == "auto":   # prefer the Dhaka-augmented baseline when it has been trained
            kind = "tfidf_lr_dhaka_aug" if (RESULTS / "tfidf_lr_dhaka_aug.joblib").exists() else "tfidf_lr"
        self.kind = kind
        if kind.startswith("tfidf_lr"):
            import joblib
            p = RESULTS / f"{kind}.joblib"
            if not p.exists():
                sys.exit(f"missing {p}: run `python -m traffictwin.nlp.train_classifier --augment-seed` first")
            self.pipe = joblib.load(p)
            self.classes = list(self.pipe.classes_)
        else:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            d = RESULTS / "distilbert/model"
            self.tok = AutoTokenizer.from_pretrained(d)
            self.model = AutoModelForSequenceClassification.from_pretrained(d).eval()
            self.torch = torch

    def __call__(self, texts: list[str]) -> list[tuple[str, float]]:
        if self.kind.startswith("tfidf_lr"):
            P = self.pipe.predict_proba(texts)
            return [(self.classes[int(row.argmax())], float(row.max())) for row in P]
        with self.torch.no_grad():
            enc = self.tok(texts, truncation=True, max_length=64, padding=True, return_tensors="pt")
            P = self.model(**enc).logits.softmax(-1)
        id2label = self.model.config.id2label
        return [(id2label[int(row.argmax())], float(row.max())) for row in P]


# ----------------------------------------------------------------------------- gazetteer
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[^\w\s#@ঀ-৿]+", " ", s)   # keep Bengali block, hashtags, handles
    return re.sub(r"\s+", " ", s).strip()


class Gazetteer:
    def __init__(self, path: Path = GAZETTEER):
        g = json.loads(path.read_text(encoding="utf-8"))
        self.places = g["places"]
        pats = []
        for i, pl in enumerate(self.places):
            for al in sorted(set([pl["name"]] + pl.get("aliases", [])), key=len, reverse=True):
                a = _norm(al)
                pats.append((len(a), re.compile(r"(?<!\w)" + re.escape(a) + r"(?!\w)"), i))
        self.pats = sorted(pats, key=lambda t: -t[0])   # longest alias first

    def find(self, text: str) -> list[dict]:
        t = _norm(text)
        hits, taken = [], []
        for _, rx, i in self.pats:
            for m in rx.finditer(t):
                if any(not (m.end() <= s or m.start() >= e) for s, e in taken):
                    continue                                  # overlaps an already-matched longer alias
                taken.append((m.start(), m.end()))
                hits.append({"place": self.places[i]["name"], "lat": self.places[i]["lat"],
                             "lon": self.places[i]["lon"], "alias": m.group(0), "pos": m.start()})
        # dedupe by place, order by position in text (first mention = primary)
        seen, out = set(), []
        for h in sorted(hits, key=lambda h: h["pos"]):
            if h["place"] not in seen:
                seen.add(h["place"]); out.append(h)
        return out


# ----------------------------------------------------------------------------- network
class Net:
    def __init__(self, path: Path = DEFAULT_NET, radius: float = RADIUS_M):
        import sumolib
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.net = sumolib.net.readNet(str(ensure_net(path)))
        (x0, y0), (x1, y1) = self.net.getBBoxXY()
        self.bbox_xy = (x0, y0, x1, y1)
        lo = self.net.convertXY2LonLat(x0, y0); hi = self.net.convertXY2LonLat(x1, y1)
        self.bbox_lonlat = (lo[0], lo[1], hi[0], hi[1])
        self.radius = radius

    def inside(self, lon: float, lat: float) -> bool:
        x, y = self.net.convertLonLat2XY(lon, lat)
        x0, y0, x1, y1 = self.bbox_xy
        return x0 <= x <= x1 and y0 <= y <= y1

    def edges_near(self, lon: float, lat: float) -> list[dict]:
        x, y = self.net.convertLonLat2XY(lon, lat)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            near = self.net.getNeighboringEdges(x, y, self.radius)
        out = []
        for e, d in sorted(near, key=lambda t: t[1]):
            if e.getFunction() == "internal":
                continue
            out.append({"id": e.getID(), "dist_m": round(float(d), 1), "name": e.getName() or "",
                        "length_m": round(e.getLength(), 1), "free_tt_s": round(e.getLength() / max(e.getSpeed(), 0.1), 1)})
        return out


# ----------------------------------------------------------------------------- pipeline
def make_events(texts: list[str], clf: Classifier, gaz: Gazetteer, net: Net | None, top_k: int = 0) -> list[dict]:
    preds = clf(texts)
    events = []
    for text, (label, conf) in zip(texts, preds):
        ev = {"text": text, "label": label, "confidence": round(conf, 4), "place": None, "lat": None,
              "lon": None, "edges": [], "factor": FACTOR.get(label, 1.0), "status": None, "places_all": []}
        hits = gaz.find(text)
        ev["places_all"] = [h["place"] for h in hits]
        if not hits:
            ev["status"] = "NO_LOCATION"
        else:
            h = hits[0]
            ev.update(place=h["place"], lat=h["lat"], lon=h["lon"], matched_alias=h["alias"])
            if net is None:
                ev["status"] = "NO_NET"
            elif not net.inside(h["lon"], h["lat"]):
                ev["status"] = "OUT_OF_NETWORK"
            else:
                near = net.edges_near(h["lon"], h["lat"])
                if top_k > 0:
                    near = near[:top_k]
                ev["edges"] = [e["id"] for e in near]
                ev["edge_details"] = near
                ev["status"] = "MAPPED" if near else "NO_EDGE_IN_RADIUS"
        if label == "irrelevant":
            ev["status"] = f"IGNORED_{ev['status']}" if ev["status"] else "IGNORED"
            ev["edges"] = []
        events.append(ev)
    return events


def write_weights(events: list[dict], base: Path, out: Path, begin: float | None, end: float | None) -> dict:
    """Apply event factors to a SUMO meanData XML; keep only id/traveltime per edge."""
    fac: dict[str, float] = {}
    free: dict[str, float] = {}
    for ev in events:
        if ev["factor"] <= 1.0 or not ev["edges"]:
            continue
        for ed in ev.get("edge_details", []) or [{"id": e} for e in ev["edges"]]:
            fac[ed["id"]] = max(fac.get(ed["id"], 1.0), ev["factor"])
            if "free_tt_s" in ed:
                free[ed["id"]] = ed["free_tt_s"]
    root_in = ET.parse(base).getroot()
    root = ET.Element("meandata")
    n_iv, n_mod, n_add = 0, 0, 0
    for iv in root_in.iter("interval"):
        b, e = float(iv.get("begin")), float(iv.get("end"))
        active = (begin is None or e > begin) and (end is None or b < end)
        o = ET.SubElement(root, "interval", begin=iv.get("begin"), end=iv.get("end"), id=iv.get("id", "ed"))
        n_iv += 1
        present = set()
        for ed in iv.iter("edge"):
            tt = ed.get("traveltime")
            if tt is None:
                continue
            eid = ed.get("id"); present.add(eid)
            v = float(tt)
            if active and eid in fac:
                v *= fac[eid]; n_mod += 1
            ET.SubElement(o, "edge", id=eid, traveltime=f"{v:.2f}")
        if active:
            for eid, f in fac.items():
                if eid not in present and eid in free:
                    ET.SubElement(o, "edge", id=eid, traveltime=f"{free[eid] * f:.2f}"); n_add += 1
    ET.indent(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(out, encoding="UTF-8", xml_declaration=True)
    return {"intervals": n_iv, "affected_edges": len(fac), "entries_scaled": n_mod, "entries_added": n_add,
            "factors": fac, "out": str(out)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="run the 20 built-in example posts")
    ap.add_argument("--text", action="append", help="classify this post (repeatable)")
    ap.add_argument("--file", help="one post per line")
    ap.add_argument("--model", choices=["auto", "tfidf_lr", "tfidf_lr_dhaka_aug", "distilbert"], default="auto",
                    help="auto = tfidf_lr_dhaka_aug if trained, else tfidf_lr")
    ap.add_argument("--top-k", type=int, default=0, help="keep only the k nearest edges per event (0 = all in radius)")
    ap.add_argument("--net", default=str(DEFAULT_NET))
    ap.add_argument("--radius", type=float, default=RADIUS_M)
    ap.add_argument("--out", default=str(RESULTS / "events.jsonl"))
    ap.add_argument("--to-weights", help="write a meanData weight XML with event factors applied")
    ap.add_argument("--base", help="base meanData XML (e.g. results/routing/static_s11_h900/edgedata.xml)")
    ap.add_argument("--events", help="events.jsonl to use for --to-weights (default: the ones produced now / --out)")
    ap.add_argument("--begin", type=float, help="apply factors only to intervals overlapping [begin,end)")
    ap.add_argument("--end", type=float)
    a = ap.parse_args()

    texts = []
    if a.demo:
        texts += DEMO_POSTS
    if a.text:
        texts += a.text
    if a.file:
        texts += [l.strip() for l in Path(a.file).read_text(encoding="utf-8").splitlines() if l.strip()]

    events = []
    if texts:
        clf, gaz = Classifier(a.model), Gazetteer()
        net = Net(Path(a.net), a.radius) if Path(a.net).exists() else None
        if net:
            print(f"[net] R1 bbox lon/lat = {tuple(round(v, 4) for v in net.bbox_lonlat)}; radius {a.radius} m")
        print(f"[clf] {clf.kind}")
        events = make_events(texts, clf, gaz, net, a.top_k)
        out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        for ev in events:
            print(f"{ev['label']:10s} {ev['confidence']:.2f}  {str(ev['place']):15s} {ev['status']:22s} "
                  f"x{ev['factor']:<4g} edges={len(ev['edges'])}  | {ev['text'][:60]}")
        n_map = sum(ev["status"] == "MAPPED" for ev in events)
        print(f"[events] {len(events)} posts -> {n_map} mapped to R1 edges; wrote {out}")

    if a.to_weights:
        if not a.base:
            ap.error("--to-weights needs --base <meandata.xml>")
        src = a.events or (a.out if events else None)
        if not events:
            if not src or not Path(src).exists():
                ap.error("--to-weights needs events: give --demo/--text/--file or --events <events.jsonl>")
            events = [json.loads(l) for l in Path(src).read_text(encoding="utf-8").splitlines() if l.strip()]
        info = write_weights(events, Path(a.base), Path(a.to_weights), a.begin, a.end)
        print(f"[weights] {info['intervals']} intervals, {info['affected_edges']} edges scaled "
              f"({info['entries_scaled']} entries x factor, {info['entries_added']} added at free-flow x factor) -> {info['out']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
