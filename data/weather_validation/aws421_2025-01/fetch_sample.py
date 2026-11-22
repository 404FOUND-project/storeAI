"""One-off validation fetch: AWS 421, 2025-01 daily data. Writes only into this folder.
Never prints or stores the service key."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
ENDPOINT = "https://apis.data.go.kr/1360000/AwsMtlyInfoService/getDailyAwsData"

key = ""
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("KMA_SERVICE_KEY="):
        key = line.split("=", 1)[1].strip().strip("\"'")
if not key:
    sys.exit("KMA_SERVICE_KEY missing")

params = {"pageNo": 1, "numOfRows": 40, "dataType": "JSON", "year": 2025, "month": "01", "station": 421}
url = ENDPOINT + "?" + urllib.parse.urlencode({**params, "ServiceKey": key})
req = urllib.request.Request(url, headers={"User-Agent": "storeAI-validation"})
status, body = None, b""
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        status, body = resp.status, resp.read()
except urllib.error.HTTPError as e:
    status, body = e.code, e.read()
except Exception as e:
    print("request error:", type(e).__name__)
    sys.exit(1)

text = body.decode("utf-8", errors="replace").replace(key, "***")
(OUT / "raw_response.txt").write_text(text, encoding="utf-8")
(OUT / "request_meta.json").write_text(json.dumps(
    {"endpoint": ENDPOINT, "params": params, "http_status": status, "bytes": len(body)}, indent=2), encoding="utf-8")
print("http_status", status, "bytes", len(body))
print(text[:600])
