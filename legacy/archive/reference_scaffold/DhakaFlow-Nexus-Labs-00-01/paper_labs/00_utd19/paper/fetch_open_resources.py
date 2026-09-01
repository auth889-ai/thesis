from pathlib import Path
import urllib.request

OUT = Path(__file__).resolve().parent
RESOURCES = {
    "Loder2019_Understanding_Traffic_Capacity.pdf": "https://www.nature.com/articles/s41598-019-51539-5.pdf",
    "Loder2019_Supplementary.pdf": "https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41598-019-51539-5/MediaObjects/41598_2019_51539_MOESM1_ESM.pdf",
    "Ambuehl2018_Resampling_MFD.pdf": "https://www.research-collection.ethz.ch/bitstreams/a3ce5a2f-d8f9-4ff4-90b9-e85f0ffecf02/download",
}
for name, url in RESOURCES.items():
    path = OUT / name
    if path.exists() and path.stat().st_size > 10_000:
        print("exists", path)
        continue
    print("downloading", url)
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
        f.write(r.read())
    print("saved", path, path.stat().st_size)
