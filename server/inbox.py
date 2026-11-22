"""Messages to an agent: written atomically to its inbox, images first, nothing at all if any image is bad."""
import base64
import binascii
import json
import os
import time

from .cells import cell_dir
from .config import IMAGE_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES, read


def decode_images(images):
    """([(ext, bytes)], error) for images sent as {type, data(base64)}."""
    images = list(images or [])
    if len(images) > MAX_IMAGES:
        return [], f"Up to {MAX_IMAGES} images per message."
    decoded = []
    for img in images:
        ext = IMAGE_TYPES.get(str(img.get("type", "")))
        if not ext:
            return [], "Images must be PNG, JPEG, GIF or WebP."
        try:
            data = base64.b64decode(str(img.get("data", "")), validate=True)
        except (binascii.Error, ValueError):
            return [], "An image could not be read."
        if len(data) > MAX_IMAGE_BYTES:
            return [], "Each image must be under 8 MB."
        decoded.append((ext, data))
    return decoded, ""


def queue_message(name, text, images=()):
    d = cell_dir(name)
    text = (text or "").strip()[:8000]
    if not d or read(d / "state" / "status") not in ("starting", "running", "idle"):
        return False, "This agent has ended."
    decoded, err = decode_images(images)
    if err:
        return False, err
    if not (text or decoded):
        return False, "Write a message or attach an image."
    box = d / "state" / "inbox"
    (box / "files").mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    saved = []
    for i, (ext, data) in enumerate(decoded):
        rel = f"files/{stamp}-{i}.{ext}"
        (box / rel).write_bytes(data)
        saved.append(rel)
    tmp = box / f".{stamp}.tmp"
    tmp.write_text(json.dumps({"text": text, "images": saved, "at": int(time.time())}))
    os.rename(tmp, box / f"{stamp}.json")
    return True, ""
