from pathlib import Path
import urllib.request

url = "https://elib.dlr.de/127994/1/08569938.pdf"
out = Path(__file__).resolve().parent / "AlvarezLopez2018_Microscopic_Traffic_Simulation_SUMO.pdf"
if not out.exists() or out.stat().st_size < 10000:
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out, "wb") as f:
        f.write(r.read())
print(out, out.stat().st_size)
