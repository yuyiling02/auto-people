"""Small OpenAI-compatible image client with explicit model selection."""

import base64
import binascii
import io
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 40 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Image service redirect refused; use the final endpoint URL.")


def checked_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("Image service URL must not contain credentials.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError("Use HTTPS, or HTTP on a loopback address only.")
    return url


def limited_read(response):
    raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise RuntimeError("Image service response exceeds 40 MB.")
    return raw


def make_ai_image(prompt, base_url, api_key, model, size=None, timeout=300):
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY before using AI rendering.")
    if timeout <= 0:
        raise ValueError("Timeout must be positive.")
    url = checked_url(base_url.rstrip("/") + "/images/generations")
    payload = {"model": model, "prompt": prompt, "n": 1}
    if size:
        payload["size"] = size
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            body = json.loads(limited_read(response))
        items = body.get("data") if isinstance(body, dict) else None
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise RuntimeError("Image response does not contain data[0].")
        item = items[0]
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"], validate=True)
        elif item.get("url"):
            # CDN image requests never inherit the API Authorization header.
            download = urllib.request.Request(checked_url(item["url"]))
            with opener.open(download, timeout=timeout) as response:
                raw = limited_read(response)
        else:
            raise RuntimeError("Image response has neither b64_json nor url.")
        with Image.open(io.BytesIO(raw)) as img:
            if img.width * img.height > 40_000_000:
                raise RuntimeError("Returned image exceeds 40 megapixels.")
            return img.convert("RGB")
    except urllib.error.HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", errors="replace").replace(api_key, "[REDACTED]")
        raise RuntimeError(f"Image request HTTP {exc.code} (model={model}): {detail[:700]}") from None
    except (socket.timeout, TimeoutError):
        raise RuntimeError("Image request timed out; no automatic paid-request retry was made.") from None
    except urllib.error.URLError:
        raise RuntimeError("Image service connection failed; check the endpoint and network.") from None
    except (json.JSONDecodeError, binascii.Error, UnidentifiedImageError, TypeError):
        raise RuntimeError("Image service returned malformed JSON or image data.") from None
