import json
import time
import urllib.request
import urllib.error

from config import BASE_URL, API_KEY, PROXY, MODEL, TEMPERATURE, MAX_TOKENS, MAX_RETRIES, RETRY_BACKOFF


def build_opener():
    handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
    return urllib.request.build_opener(handler)


def chat(prompt, max_tokens=MAX_TOKENS):
    url = BASE_URL.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + API_KEY,
        "Content-Type": "application/json",
    }
    last_err = None
    for attempt in range(MAX_RETRIES):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with build_opener().open(req, timeout=120) as resp:
                data = json.load(resp)
            usage = data.get("usage", {})
            det = usage.get("completion_tokens_details", {})
            return {
                "ok": True,
                "content": data["choices"][0]["message"]["content"],
                "model": data.get("model"),
                "reasoning_tokens": det.get("reasoning_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "elapsed": time.time() - t0,
            }
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:300]
            last_err = f"HTTP {e.code}: {detail}"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF * (attempt + 1))
    return {"ok": False, "content": "", "error": last_err}
