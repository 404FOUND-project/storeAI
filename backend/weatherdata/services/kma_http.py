"""Small, bounded JSON GET helper for data.go.kr (retries, timeout, key redaction)."""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)
RETRY_WAIT_SECONDS = (2.0, 5.0)
TIMEOUT_SECONDS = 15


class KmaRequestError(Exception):
    def __init__(self, code, message, result_code=""):
        super().__init__(message)
        self.code, self.result_code = code, result_code


def get_json(url, params, key, *, opener=urllib.request.urlopen, sleep=time.sleep):
    """GET url?params&serviceKey=key; returns (items, result_code). Never leaks the key."""
    if not key:
        raise KmaRequestError("configuration_error", "KMA_SERVICE_KEY is not configured.")
    full = url + "?" + urllib.parse.urlencode({**params, "serviceKey": key})
    last = None
    for attempt in range(len(RETRY_WAIT_SECONDS) + 1):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "storeAI"})
            with opener(req, timeout=TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            header = payload["response"]["header"]
            code = str(header.get("resultCode", ""))
            if code != "00":
                # NODATA_ERROR (03) etc. are not transient: do not retry.
                raise KmaRequestError("api_error", f"KMA resultCode={code} {header.get('resultMsg', '')}", code)
            items = payload["response"]["body"].get("items") or {}
            items = items.get("item", []) if isinstance(items, dict) else []
            return (items if isinstance(items, list) else [items]), code
        except KmaRequestError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
            last = KmaRequestError("request_error", f"{type(exc).__name__} while calling KMA")
            logger.warning("KMA request failed (attempt %d, %s)", attempt + 1, type(exc).__name__)
            if attempt < len(RETRY_WAIT_SECONDS):
                sleep(RETRY_WAIT_SECONDS[attempt])
    raise last
