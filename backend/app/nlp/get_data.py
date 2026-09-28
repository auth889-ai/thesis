#!/usr/bin/env python3
"""Obtain the labelled traffic-incident TEXT corpus and freeze train/val/test splits.

    python -m app.nlp.get_data               # download real corpus, write data/nlp/{train,val,test}.csv + MANIFEST.json
    python -m app.nlp.get_data --seed-only   # (fallback) build splits from the 150-post hand-written Dhaka seed set

Primary source (REAL data, used by default)
-------------------------------------------
Dabiri, S. (2018). "Tweets with traffic-related labels for developing a Twitter-based traffic
information system". Mendeley Data, v1. doi:10.17632/c3xvj5snvv.1 — licence **CC BY 4.0**.
Companion paper: Dabiri & Heaslip (2019), "Developing a Twitter-based traffic event detection
model using deep learning architectures", Expert Systems with Applications 118, 425-439.
Files 1_TrainingSet_3Class.csv / 1_TestSet_3Class.csv are header-less CSVs with columns
(label, tweet_id, text). Original labels -> ours:
    0  Non-traffic                        -> irrelevant
    1  Traffic incident (crash, disabled  -> incident
       vehicle, closure, ...)
    2  Traffic conditions & information   -> congestion
       (rush hour, congestion, slow)
The authors' own test set is kept as our held-out TEST; their training set is split 90/10
(stratified, seed 20260901) into TRAIN / VAL. Exact-duplicate texts are dropped (first kept).

Fallback (only if the download fails or --seed-only): data/nlp/dhaka_seed.csv, ~150 hand-written
Dhaka-style English/Banglish posts labelled by the author of this script; MANIFEST then says
`source: SYNTHETIC_SEED — replace on Day 1`. The seed file is ALWAYS written because
train_classifier.py also uses it as an out-of-domain (Dhaka) probe.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
from app.paths import REPO
DATA = REPO / "data/nlp"
RAW = DATA / "raw"
SEED = 20260901
LABELS = ["incident", "congestion", "irrelevant"]

MENDELEY = {
    "dataset": "c3xvj5snvv",
    "version": 1,
    "doi": "10.17632/c3xvj5snvv.1",
    "url": "https://data.mendeley.com/datasets/c3xvj5snvv/1",
    "licence": "CC BY 4.0",
    "citation": ("Dabiri, S. (2018). Tweets with traffic-related labels for developing a "
                 "Twitter-based traffic information system. Mendeley Data, v1. "
                 "https://doi.org/10.17632/c3xvj5snvv.1"),
    "files": {
        "1_TrainingSet_3Class.csv": {
            "url": "https://data.mendeley.com/public-files/datasets/c3xvj5snvv/files/"
                   "312d3cb8-863b-4677-82de-0874d770f9e9/file_downloaded",
            "sha256": "6afba982acaff9bb7bee28c10c0df7af5337819b49164043e14f2a318375a566",
        },
        "1_TestSet_3Class.csv": {
            "url": "https://data.mendeley.com/public-files/datasets/c3xvj5snvv/files/"
                   "c93b72b0-8ace-432c-90ee-e118d43a6965/file_downloaded",
            "sha256": "169265807345d692ae7974960fcddfd0a3fc398e93a2f788c8b2652aa38212d7",
        },
    },
}
LABEL_MAP = {0: "irrelevant", 1: "incident", 2: "congestion"}

# ----------------------------------------------------------------------------------------------
# Hand-written Dhaka seed set (English / Banglish). Labelled by the script author. 150 posts.
# incident  = non-recurring event that blocks/obstructs a road (crash, breakdown, closure, fire,
#             blockade, flooding)   -> routing: treat edge as blocked
# congestion= recurring/flow condition (jam, slow, heavy traffic, stuck)   -> routing: slow edge
# irrelevant= everything else (no actionable road state)
# ----------------------------------------------------------------------------------------------
DHAKA_SEED = [
    # ---- incident (50)
    ("incident", "Bus and CNG collision at Karwan Bazar signal, one lane blocked, police on the spot"),
    ("incident", "Accident near Farmgate overbridge, ambulance came, road partially closed"),
    ("incident", "Truck overturned on Bijoy Sarani, road blocked towards Jahangir Gate"),
    ("incident", "Shahbagh intersection fully blocked by protesters, avoid the area"),
    ("incident", "Bangla Motor e ekta private car ulte gese, rasta bondho"),
    ("incident", "Panthapath: a CNG caught fire near Square Hospital, traffic stopped"),
    ("incident", "Cover van broke down in the middle of Mohakhali flyover, right lane closed"),
    ("incident", "Kakrail mosque er samne bus accident, ekhon rasta pura block"),
    ("incident", "Moghbazar flyover ramp closed due to a crane accident, use alternative route"),
    ("incident", "Malibagh rail crossing: train stuck, gates down for 30 min, cars piling up"),
    ("incident", "Road cave-in at Dhanmondi 27, WASA digging, whole road closed"),
    ("incident", "Science Lab: student blockade, no vehicles moving in any direction"),
    ("incident", "New Market er samne rickshaw-bus dhakka, driver injured, rasta atke gese"),
    ("incident", "Elephant Road closed for a political procession, police diverting traffic"),
    ("incident", "Gulistan flyover: motorcycle crash, two lanes blocked"),
    ("incident", "Motijheel Shapla Chattar blocked by a garment workers' rally since 10am"),
    ("incident", "Paltan e bus e aagun, fire service asche, road bondho"),
    ("incident", "Press Club er samne manob bondhon, rasta half block"),
    ("incident", "Hatirjheel link road: car fell into the drain, rescue ongoing, road closed"),
    ("incident", "Tejgaon truck stand: two trucks collided, Satrasta road blocked"),
    ("incident", "Sonargaon crossing accident, bus hit a divider, one lane shut"),
    ("incident", "Kawran Bazar e truck ulte gese, sobji er truck, rasta pura block"),
    ("incident", "Waterlogging at Mouchak, cars stalled in knee-deep water, road impassable"),
    ("incident", "Green Road under water after the rain, vehicles stuck, not passable"),
    ("incident", "Bashundhara City er samne gas line leak, police closed the road"),
    ("incident", "Bijoy Sarani signal broken down and a bus collided with a car, big mess"),
    ("incident", "Mirpur Road at Asad Gate: bus lost control, hit the footpath, road blocked"),
    ("incident", "Nilkhet: book market fire, fire trucks blocking Azimpur road"),
    ("incident", "Shantinagar e manhole khola, ekta CNG pore gese, rasta bondho"),
    ("incident", "Bailey Road closed after building fire, all vehicles diverted"),
    ("incident", "Chankharpul flyover ramp: pickup overturned, right lane closed"),
    ("incident", "Farmgate: metro rail construction crane fell, Kazi Nazrul Islam Avenue blocked"),
    ("incident", "Shahbagh e ambulance-bus collision, emergency lane o block"),
    ("incident", "Tejgaon Nabisco: container truck stuck under the rail bridge, road closed"),
    ("incident", "Jahangir Gate: army checkpost blocking two lanes due to VIP movement"),
    ("incident", "Kalabagan road dug up by WASA overnight, no passage today"),
    ("incident", "Dhanmondi 32 e private car accident, road ek dik bondho"),
    ("incident", "Ramna park side road closed for a state programme, police barricades"),
    ("incident", "Matsya Bhaban: police barricade, road to Press Club fully closed"),
    ("incident", "Gulistan e bus er sathe leguna er dhakka, tin jon ahoto, rasta block"),
    ("incident", "Mohakhali bus terminal er samne bus ulte gese, Airport road ek lane bondho"),
    ("incident", "Moghbazar: electric pole fell on the road after the storm, road closed"),
    ("incident", "Malibagh chowdhury para road blocked by a stalled garbage truck"),
    ("incident", "Elephant Road e student der blockade, kono gari jacche na"),
    ("incident", "Azimpur: CNG hit a rickshaw, road half closed, police clearing"),
    ("incident", "Paltan crossing: bomb scare, police cordon, no traffic allowed"),
    ("incident", "Panthapath signal e tree fell on a bus, road blocked both ways"),
    ("incident", "New Market e agun legeche, fire service er gari te rasta bondho"),
    ("incident", "Kakrail: car crash into the divider, one lane closed towards Shantinagar"),
    ("incident", "Sonargaon hotel er samne pickup ulte gese, Karwan Bazar er dike rasta block"),
    # ---- congestion (50)
    ("congestion", "Heavy jam from Farmgate to Karwan Bazar, 40 minutes for 1 km"),
    ("congestion", "Shahbagh theke Bangla Motor porjonto puro jam, 1 ghonta dhore boshe asi"),
    ("congestion", "Mohakhali flyover e bhoyonkor jam, ekdom norche na"),
    ("congestion", "Bijoy Sarani signal is taking forever, long queue back to Jahangir Gate"),
    ("congestion", "Gulistan er jam ajke onek beshi, office time e ber hoyen na"),
    ("congestion", "Slow moving traffic on Panthapath towards Science Lab"),
    ("congestion", "Kakrail to Moghbazar bumper to bumper as usual"),
    ("congestion", "Malibagh rail gate er jonno lomba jam, 20 min wait"),
    ("congestion", "Dhanmondi 27 e jam, Mirpur Road pura atka"),
    ("congestion", "New Market area e crazy jam, shopping rush"),
    ("congestion", "Elephant Road slow, took 25 min from Science Lab to Bata signal"),
    ("congestion", "Motijheel office hours jam, Shapla Chattar theke Paltan porjonto"),
    ("congestion", "Press Club er samne slow traffic, aste aste jacche"),
    ("congestion", "Hatirjheel link road e jam ajke, rain er karone"),
    ("congestion", "Tejgaon Satrasta te truck er line, gari norche na"),
    ("congestion", "Sonargaon crossing e signal e 15 minute ore boshe asi"),
    ("congestion", "Karwan Bazar er jam ekhon Farmgate porjonto giye thekeche"),
    ("congestion", "Mouchak market er samne jam, Malibagh dike ekdom slow"),
    ("congestion", "Green Road e onek jam, Panthapath signal er jonno"),
    ("congestion", "Bashundhara City er samne shopping traffic, rasta slow"),
    ("congestion", "Asad Gate theke Dhanmondi 27 porjonto heavy traffic"),
    ("congestion", "Nilkhet e jam, Azimpur er dike gari norche na"),
    ("congestion", "Shantinagar to Kakrail 30 min today, terrible"),
    ("congestion", "Bailey Road jam, Shantinagar er dike lomba line"),
    ("congestion", "Chankharpul e slow traffic, Gulistan er dike jam"),
    ("congestion", "Farmgate overbridge er niche bus er line, 2 signal miss korlam"),
    ("congestion", "Shahbagh jam ajke normal er cheye beshi, 45 minute"),
    ("congestion", "Tejgaon Nabisco e heavy congestion, Mohakhali er dike"),
    ("congestion", "Jahangir Gate signal e long queue, Bijoy Sarani er dike"),
    ("congestion", "Kalabagan e slow traffic, Mirpur Road er cheye kharap"),
    ("congestion", "Dhanmondi 32 er samne jam, school chhutir time"),
    ("congestion", "Ramna area e traffic slow, Matsya Bhaban signal e wait"),
    ("congestion", "Paltan e jam, Gulistan theke Press Club porjonto"),
    ("congestion", "Mohakhali te bus terminal er jonno jam, Airport road slow"),
    ("congestion", "Moghbazar flyover e jam, Mouchak er dike ekdom atka"),
    ("congestion", "Malibagh e bumper to bumper, Rampura er dike jete parchi na"),
    ("congestion", "Elephant Road e Eid shopping jam, gari norche na"),
    ("congestion", "Azimpur e jam, New Market er dike slow"),
    ("congestion", "Gridlock at Panthapath signal, Square Hospital er samne"),
    ("congestion", "Karwan Bazar traffic at a standstill, 30 mins and not moving"),
    ("congestion", "Bangla Motor signal e 3 bar wait korte holo, onek jam"),
    ("congestion", "Science Lab crossing jam, Dhanmondi er dike slow"),
    ("congestion", "Kakrail e jam, church er samne theke Shantinagar porjonto"),
    ("congestion", "Sonargaon signal e slow, Karwan Bazar er dike lomba line"),
    ("congestion", "Bijoy Sarani te jam ajke, Farmgate er dike norche na"),
    ("congestion", "Gulistan flyover slow, Motijheel er dike traffic heavy"),
    ("congestion", "Farmgate bus stand e jam, Tejgaon er dike slow"),
    ("congestion", "Hatirjheel Moghbazar exit e jam, rush hour"),
    ("congestion", "Shahbagh theke Press Club, slow traffic, Ramna signal er jonno"),
    ("congestion", "New Market e rasta pura atka, Nilkhet er dike o jam"),
    # ---- irrelevant (50)
    ("irrelevant", "Best biryani near Karwan Bazar? Looking for suggestions"),
    ("irrelevant", "Shahbagh er boi mela te ajke onek bhir, valo lagche"),
    ("irrelevant", "New phone launch at Bashundhara City today, huge discount"),
    ("irrelevant", "Farmgate coaching center e admission cholche"),
    ("irrelevant", "Dhanmondi lake e sondha bela hata onek shanti"),
    ("irrelevant", "Metro rail is the best thing that happened to Dhaka"),
    ("irrelevant", "Rain in Dhaka today, finally some relief from the heat"),
    ("irrelevant", "Bangladesh won the match! Celebration at TSC tonight"),
    ("irrelevant", "Gulistan e cheap cloth market, valo deal paisi"),
    ("irrelevant", "New cafe opened at Elephant Road, nice coffee"),
    ("irrelevant", "Traffic police uniform new design dekhlam, valo lagse"),
    ("irrelevant", "Job circular: driver wanted for a company in Motijheel"),
    ("irrelevant", "Hatirjheel e rat er belay lighting osadharon"),
    ("irrelevant", "Mohakhali te new hospital opening next month"),
    ("irrelevant", "Panthapath er Square hospital er doctor onek valo"),
    ("irrelevant", "Kakrail church e Christmas program"),
    ("irrelevant", "Moghbazar e bhalo pizza kothay pawa jay?"),
    ("irrelevant", "Malibagh e flat bhara, 2 bed, contact korun"),
    ("irrelevant", "Science Lab er samne fuchka khaisi ajke"),
    ("irrelevant", "Press Club e seminar on road safety awareness next week"),
    ("irrelevant", "Bijoy Sarani te novo theatre te show dekhlam"),
    ("irrelevant", "Tejgaon industrial area te factory job vacancy"),
    ("irrelevant", "Sonargaon hotel er buffet onek dami"),
    ("irrelevant", "Happy birthday to my friend from Dhanmondi 27"),
    ("irrelevant", "Good morning Dhaka, have a nice day everyone"),
    ("irrelevant", "Government announced new bus fare from next month"),
    ("irrelevant", "Ride sharing app er promo code share korun"),
    ("irrelevant", "Nilkhet e purano boi kinlam, 50 taka te"),
    ("irrelevant", "Azimpur graveyard e gelam ajke"),
    ("irrelevant", "Shantinagar bazar e ilish mach er dam onek beshi"),
    ("irrelevant", "Bailey Road er natok para te new play"),
    ("irrelevant", "Chankharpul e Dhaka Medical e doctor der strike"),
    ("irrelevant", "BRTA driving licence exam ajke dilam, pass korsi"),
    ("irrelevant", "Paltan maidan e political rally announced for Friday"),
    ("irrelevant", "Jahangir Gate er kache army museum visit korlam"),
    ("irrelevant", "Kalabagan e cricket khela dekhte gelam"),
    ("irrelevant", "Ramna park e morning walk group join korun"),
    ("irrelevant", "Matsya Bhaban er kache new office khulse amader"),
    ("irrelevant", "Green Road e bhalo tailor ase?"),
    ("irrelevant", "Mouchak market e Eid collection asche"),
    ("irrelevant", "Asad Gate er kache Aarong e sale cholche"),
    ("irrelevant", "Bangla Motor e ekta bhalo restaurant khulse"),
    ("irrelevant", "Weather forecast: thunderstorm expected over Dhaka tomorrow"),
    ("irrelevant", "Karwan Bazar er sobji er dam ajke kom"),
    ("irrelevant", "Motijheel stock market ajke porse"),
    ("irrelevant", "Farmgate e bhalo photocopy dokan kothay?"),
    ("irrelevant", "Traffic week starts Monday, police will give safety leaflets"),
    ("irrelevant", "Gulistan e new bus service to Chittagong"),
    ("irrelevant", "Loved the sunset from Hatirjheel bridge today"),
    ("irrelevant", "Dhaka University admission result published"),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest: Path, expected_sha: str) -> None:
    if dest.exists() and sha256_file(dest) == expected_sha:
        print(f"[get_data] cached  {dest.name}")
        return
    print(f"[get_data] downloading {dest.name} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "dhakaflow-src/pipeline/nlp/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    got = sha256_file(dest)
    if got != expected_sha:
        raise RuntimeError(f"sha256 mismatch for {dest.name}: got {got}, expected {expected_sha}")


def read_mendeley_csv(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, header=None, names=["orig_label", "tweet_id", "text"],
                     encoding="utf-8", encoding_errors="replace", dtype={"orig_label": "Int64"})
    df = df.dropna(subset=["orig_label", "text"])
    df["orig_label"] = df["orig_label"].astype(int)
    df["label"] = df["orig_label"].map(LABEL_MAP)
    df["text"] = df["text"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    df = df[df["text"].str.len() > 0]
    return df[["text", "label", "orig_label"]]


def write_splits(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, df in [("train", train), ("val", val), ("test", test)]:
        p = DATA / f"{name}.csv"
        df[["text", "label"]].to_csv(p, index=False)
        out[name] = {"path": str(p.relative_to(HERE.parent)), "rows": int(len(df)),
                     "sha256": sha256_file(p),
                     "per_class": {k: int(v) for k, v in df["label"].value_counts().sort_index().items()}}
    return out


def write_seed() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(DHAKA_SEED, columns=["label", "text"])[["text", "label"]]
    p = DATA / "dhaka_seed.csv"
    df.to_csv(p, index=False)
    return {"path": str(p.relative_to(HERE.parent)), "rows": int(len(df)), "sha256": sha256_file(p),
            "per_class": {k: int(v) for k, v in df["label"].value_counts().sort_index().items()},
            "note": "hand-written Dhaka English/Banglish posts, labelled by the script author; "
                    "used as an out-of-domain probe (and as the fallback corpus)."}


def build_real() -> tuple[dict, dict]:
    from sklearn.model_selection import train_test_split
    raw_info = {}
    for fname, meta in MENDELEY["files"].items():
        dest = RAW / fname
        download(meta["url"], dest, meta["sha256"])
        raw_info[fname] = {"sha256": meta["sha256"], "bytes": dest.stat().st_size, "url": meta["url"]}
    tr = read_mendeley_csv(RAW / "1_TrainingSet_3Class.csv")
    te = read_mendeley_csv(RAW / "1_TestSet_3Class.csv")
    n_tr0, n_te0 = len(tr), len(te)
    # exact-duplicate texts: keep first occurrence, prefer the test set's copy stays in test
    te = te.drop_duplicates("text")
    tr = tr[~tr["text"].isin(set(te["text"]))].drop_duplicates("text")
    train, val = train_test_split(tr, test_size=0.10, random_state=SEED, stratify=tr["label"])
    train = train.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    val = val.reset_index(drop=True)
    test = te.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    splits = write_splits(train, val, test)
    manifest = {
        "source": "REAL",
        "name": "Tweets with traffic-related labels for developing a Twitter-based traffic information system",
        "provider": "Mendeley Data",
        "doi": MENDELEY["doi"], "url": MENDELEY["url"], "licence": MENDELEY["licence"],
        "citation": MENDELEY["citation"],
        "paper": "Dabiri & Heaslip (2019) Expert Systems with Applications 118:425-439, "
                 "doi:10.1016/j.eswa.2018.10.017",
        "raw_files": raw_info,
        "label_mapping": {"0 Non-traffic": "irrelevant", "1 Traffic incident": "incident",
                          "2 Traffic conditions and information": "congestion"},
        "split_rule": ("authors' 3-class test set = TEST (held out, never used for fitting); "
                       "authors' training set -> TRAIN/VAL 90/10 stratified, random_state=20260901; "
                       "exact-duplicate texts dropped (test copy wins)"),
        "rows_raw": {"train_file": n_tr0, "test_file": n_te0},
        "splits": splits,
    }
    return manifest, splits


def build_seed_fallback(reason: str) -> dict:
    from sklearn.model_selection import train_test_split
    df = pd.DataFrame(DHAKA_SEED, columns=["label", "text"])[["text", "label"]]
    tr, te = train_test_split(df, test_size=0.2, random_state=SEED, stratify=df["label"])
    tr, va = train_test_split(tr, test_size=0.15, random_state=SEED, stratify=tr["label"])
    splits = write_splits(tr.reset_index(drop=True), va.reset_index(drop=True), te.reset_index(drop=True))
    return {"source": "SYNTHETIC_SEED — replace on Day 1", "reason": reason,
            "licence": "hand-written by the repository author (no external licence)",
            "label_mapping": {"as labelled": "incident|congestion|irrelevant"},
            "split_rule": "150 seed posts -> 68/12/20 % stratified, random_state=20260901",
            "splits": splits}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed-only", action="store_true", help="skip download; build splits from the Dhaka seed set")
    a = ap.parse_args()

    seed_info = write_seed()
    manifest = None
    if not a.seed_only:
        try:
            manifest, _ = build_real()
        except Exception as e:  # network down, URL moved, checksum mismatch ...
            print(f"[get_data] REAL corpus unavailable: {e!r}\n[get_data] falling back to SYNTHETIC_SEED",
                  file=sys.stderr)
            manifest = build_seed_fallback(repr(e))
    else:
        manifest = build_seed_fallback("--seed-only")
    manifest["labels"] = LABELS
    manifest["dhaka_seed"] = seed_info
    manifest["created_by"] = "python -m app.nlp.get_data"
    (DATA / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"[get_data] source = {manifest['source']}")
    for k, v in manifest["splits"].items():
        print(f"[get_data] {k:5s} rows={v['rows']:6d} {v['per_class']} sha256={v['sha256'][:12]}")
    print(f"[get_data] wrote {DATA / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
