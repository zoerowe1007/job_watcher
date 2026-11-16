"""Tiny JSON-over-HTTP helper (standard library only)."""
import gzip
import json
import time
import urllib.error
import urllib.request

USER_AGENT = "job-watcher/1.0 (student project; https://github.com/zoerowe1007/job_watcher)"


class HttpError(Exception):
    """A request that failed after retries."""


def request_json(url, data=None, headers=None, timeout=45, retries=3, sleep=time.sleep):
    """GET (data=None) or POST (data=dict -> JSON body) and return parsed JSON.

    Retries on network errors, 429 and 5xx with a growing pause.
    """
    hdrs = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    payload = gzip.decompress(payload)
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} from {url}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = f"{type(e).__name__}: {e} ({url})"
        except ValueError as e:  # bad JSON
            last = f"response was not JSON ({url}): {e}"
            break
        if attempt < retries - 1:
            sleep(2 ** attempt)
    raise HttpError(last or f"request failed: {url}")
