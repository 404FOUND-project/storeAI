"""Fetch AWS 421 monthly daily-data 2025-01..2026-10. Writes only into aws421_full/. Never prints/stores key."""
import json, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ENDPOINT = "https://apis.data.go.kr/1360000/AwsMtlyInfoService/getDailyAwsData"
key = ""
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("KMA_SERVICE_KEY="):
        key = line.split("=", 1)[1].strip().strip("\"'")
if not key: sys.exit("KMA_SERVICE_KEY missing")
months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 11)]
meta = []
for y, m in months:
    f = OUT / "raw" / f"raw_{y}-{m:02d}.json"
    if f.exists():
        print(y, m, "raw exists, skip"); continue
    params = {"pageNo": 1, "numOfRows": 40, "dataType": "JSON", "year": y, "month": f"{m:02d}", "station": 421}
    url = ENDPOINT + "?" + urllib.parse.urlencode({**params, "ServiceKey": key})
    req = urllib.request.Request(url, headers={"User-Agent": "storeAI-validation"})
    status, body = None, b""
    try:
        with urllib.request.urlopen(req, timeout=30) as r: status, body = r.status, r.read()
    except urllib.error.HTTPError as e: status, body = e.code, e.read()
    except Exception as e:
        status = f"error:{type(e).__name__}"
    text = body.decode("utf-8", errors="replace").replace(key, "***")
    f.write_text(text, encoding="utf-8")
    meta.append({"year": y, "month": m, "http_status": status, "bytes": len(body)})
    print(y, m, status, len(body)); time.sleep(0.5)
(OUT / "raw" / "request_meta_fetch.json").write_text(json.dumps({"endpoint": ENDPOINT, "params_template": {"numOfRows": 40, "dataType": "JSON", "station": 421}, "calls": meta}, indent=1), encoding="utf-8")
