"""Full walkthrough video, part 2 of 2: compose the recordings into one file with ffmpeg.

    python scripts/demo/video.py

Reads evidence/demo/raw/ (phone.webm, desktop.webm, sumo_frames/, events.json and the caption/title PNGs, all written by
frontend/tests/qa/walkthrough.cjs and scripts/demo/ambulance.py --record). Writes evidence/demo/:
  segments/NN_name.mp4                     one file per chapter (2 s title card, then the clip with its captions)
  full_walkthrough.mp4                     all chapters, with embedded chapter marks
  full_walkthrough.{en,bn}.srt             the same captions and spoken lines as subtitles
  chapters.txt                             chapter start times
  frames/NN_name.png                       one frame from the middle of each chapter, for checking by eye
  walkthrough_record.json                  durations, failed steps, page errors, hashes
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "evidence/demo"
RAW = DEMO / "raw"
W, H, FPS, TITLE_S, SAY_S, SUMO_FPS = 1920, 1080, 30, 2.0, 3.0, 8
BG = "0x0e1a2b"
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-r", str(FPS)]


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def duration(f: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout
    return float(out.strip())


def chapters(events: list[dict], lengths: dict[str, float]) -> list[dict]:
    """Each chapter: its video, start and end on that video's clock, and the captions and spoken lines inside it. Pure."""
    segs = [e for e in events if e["kind"] == "seg"]
    out = []
    for i, s in enumerate(segs):
        nxt = next((x for x in segs[i + 1:] if x["video"] == s["video"]), None)
        end = nxt["t"] if nxt else lengths[s["video"]]
        inside = [e for e in events if e["video"] == s["video"] and e["kind"] in ("cap", "say") and s["t"] - 0.01 <= e["t"] < end]
        out.append({**s, "start": s["t"], "end": end, "items": inside})
    return out


def windows(items: list[dict], start: float, end: float) -> list[tuple[dict, float, float]]:
    """(item, from, to) on the chapter clock: a caption until the next caption, a spoken line for SAY_S seconds. Pure."""
    caps = [e for e in items if e["kind"] == "cap"]
    out = []
    for i, c in enumerate(caps):
        out.append((c, c["t"] - start, (caps[i + 1]["t"] if i + 1 < len(caps) else end) - start))
    says = [e for e in items if e["kind"] == "say"]
    for i, s in enumerate(says):
        to = min(s["t"] + SAY_S, says[i + 1]["t"] if i + 1 < len(says) else end, end)
        out.append((s, s["t"] - start, to - start))
    return out


def clip(ch: dict, out: Path) -> None:
    v = ch["video"]
    if v == "sumo":
        src = ["-framerate", str(SUMO_FPS), "-i", str(RAW / "sumo_frames/f%05d.png")]
        place, layout = f"[0:v]scale={W}:{H - 190}:force_original_aspect_ratio=decrease,setpts=PTS-STARTPTS[v];[bg][v]overlay=(W-w)/2:0:shortest=1[b0]", "bottom"
    else:
        src = ["-ss", f"{ch['start']:.3f}", "-to", f"{ch['end']:.3f}", "-i", str(RAW / f"{v}.webm")]
        if v == "phone":
            place, layout = f"[0:v]scale=-2:{H - 40},setpts=PTS-STARTPTS[v];[bg][v]overlay=90:20:shortest=1[b0]", "side"
        else:
            place, layout = f"[0:v]scale=-2:{H - 190},setpts=PTS-STARTPTS[v];[bg][v]overlay=(W-w)/2:0:shortest=1[b0]", "bottom"
    wins = windows(ch["items"], ch["start"] if v != "sumo" else 0, ch["end"] if v != "sumo" else 1e9)
    inputs, graph, last = [], [f"color=c={BG}:s={W}x{H}:r={FPS}[bg]", place], "b0"
    for k, (e, a, b) in enumerate(wins, start=1):
        png = RAW / e[f"png_{layout}"]
        h = Image.open(png).height
        if layout == "side":
            x, y = 640, (620 if e["kind"] == "cap" else 140)
        else:
            x, y = 0, (H - h if e["kind"] == "cap" else H - h - 70)
        inputs += ["-i", str(png)]
        graph.append(f"[{last}][{k}:v]overlay={x}:{y}:enable='between(t,{max(a, 0):.2f},{b:.2f})'[b{k}]")
        last = f"b{k}"
    ff(*src, *inputs, "-filter_complex", ";".join(graph), "-map", f"[{last}]", "-an", *ENC, str(out))


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg is needed: brew install ffmpeg"); return 1
    ev = json.loads((RAW / "events.json").read_text())
    events = ev["events"]
    lengths = {v: duration(RAW / f"{v}.webm") for v in ("phone", "desktop")}
    lengths["sumo"] = len(list((RAW / "sumo_frames").glob("f*.png"))) / SUMO_FPS
    for d in ("segments", "frames"):
        shutil.rmtree(DEMO / d, ignore_errors=True)
        (DEMO / d).mkdir(parents=True)
    tmp = DEMO / "segments/.parts"
    tmp.mkdir()
    chs = chapters(events, lengths)
    offset, rows, en, bn, meta = 0.0, [], [], [], [";FFMETADATA1"]
    for n, ch in enumerate(chs, start=1):
        title, body, seg = tmp / f"{ch['id']}_title.mp4", tmp / f"{ch['id']}_clip.mp4", DEMO / f"segments/{ch['id']}.mp4"
        ff("-loop", "1", "-t", str(TITLE_S), "-i", str(RAW / ch["png"]), "-vf", f"scale={W}:{H}", "-an", *ENC, str(title))
        clip(ch, body)
        lst = tmp / f"{ch['id']}.txt"
        lst.write_text(f"file '{title}'\nfile '{body}'\n")
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(seg))
        d = duration(seg)
        ff("-ss", f"{TITLE_S + (d - TITLE_S) / 2:.2f}", "-i", str(seg), "-frames:v", "1", str(DEMO / f"frames/{ch['id']}.png"))
        en.append((offset, offset + TITLE_S, ch["en"])); bn.append((offset, offset + TITLE_S, ch["bn"]))
        for e, a, b in windows(ch["items"], ch["start"] if ch["video"] != "sumo" else 0, ch["end"] if ch["video"] != "sumo" else d - TITLE_S):
            a0, b0 = offset + TITLE_S + max(a, 0), offset + TITLE_S + min(b, d - TITLE_S)
            if e["kind"] == "cap":
                en.append((a0, b0, e["en"] + (f"\n[{e['src']}]" if e.get("src") else ""))); bn.append((a0, b0, e["bn"]))
            else:
                en.append((a0, b0, f"(spoken, Bangla) {e['text']}")); bn.append((a0, b0, f"(বলা হলো) {e['text']}"))
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(offset * 1000)}", f"END={int((offset + d) * 1000)}", f"title={ch['en']} / {ch['bn']}"]
        rows.append({"chapter": n, "id": ch["id"], "title_en": ch["en"], "title_bn": ch["bn"], "start_s": round(offset, 2), "duration_s": round(d, 2),
                     "file": f"segments/{ch['id']}.mp4", "frame": f"frames/{ch['id']}.png"})
        offset += d
        print(f"{n:>2} {ch['id']:<16} {d:6.1f} s", flush=True)
    lst = tmp / "all.txt"
    lst.write_text("".join(f"file '{DEMO / r['file']}'\n" for r in rows))
    (tmp / "meta.txt").write_text("\n".join(meta) + "\n")
    full = DEMO / "full_walkthrough.mp4"
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(tmp / "meta.txt"), "-map_metadata", "1", "-map_chapters", "1", "-c", "copy", str(full))
    shutil.rmtree(tmp)
    for name, subs in (("en", en), ("bn", bn)):
        subs = sorted(subs)
        (DEMO / f"full_walkthrough.{name}.srt").write_text("".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(subs, start=1)))
    (DEMO / "chapters.txt").write_text("".join(f"{int(r['start_s'] // 60)}:{int(r['start_s'] % 60):02d}  {r['title_en']} / {r['title_bn']}\n" for r in rows))
    total = duration(full)
    rec = {"label": "walkthrough of the web app (local server) and the SUMO demo", "base": ev["base"], "recorded": ev["when"], "total_s": round(total, 1),
           "chapters": rows, "failed_steps": [e for e in events if e["kind"] == "fail"], "page_errors": [e for e in events if e["kind"] == "page_errors"],
           "spoken_lines": sum(e["kind"] == "say" for e in events), "api": [e for e in events if e["kind"] == "api"],
           "sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in (full, DEMO / "full_walkthrough.en.srt", DEMO / "full_walkthrough.bn.srt")}}
    (DEMO / "walkthrough_record.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    print(f"total {total / 60:.1f} min, {len(rows)} chapters, failed steps {len(rec['failed_steps'])}: {full.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
