"""Scraper utility functions: user-agent rotation, delays, retries."""

import asyncio
import random
from typing import Optional

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
]


def get_random_user_agent() -> str:
    """Return a random user-agent string."""
    return random.choice(USER_AGENTS)


async def random_delay(min_seconds: int = 2, max_seconds: int = 5) -> None:
    """Sleep for a random duration between min and max seconds."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def retry_with_backoff(
    coro_func,
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    **kwargs,
) -> Optional[any]:
    """
    Retry an async function with exponential backoff.

    Args:
        coro_func: The async function to call.
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds for exponential backoff.

    Returns:
        The result of the coroutine, or None if all retries failed.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait)
    raise last_exception


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename."""
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    return "".join(c if c in keep else "_" for c in name)


def has_dealer_frame(img_bytes: bytes) -> bool:
    """Detect if a JPEG image has the Automotive Avenues dealer frame overlay.

    The frame consists of:
    - Top-left: White rounded rectangle with "AUTOMOTIVE Avenues" logo (~13% height)
    - Bottom-right: White bar with "www.automotiveavenuesnj.com" (~7% height)
    - Small blue swoosh accents in corners

    Returns True if the frame is detected.
    """
    import numpy as np
    from PIL import Image
    from io import BytesIO

    try:
        img = Image.open(BytesIO(img_bytes))
        arr = np.array(img)
        h, w = arr.shape[:2]
        if h < 100 or w < 100:
            return False

        # Check top-left area for white/bright region (logo background)
        tl_h, tl_w = int(h * 0.12), int(w * 0.30)
        tl = arr[0:tl_h, 0:tl_w, :]
        tl_white = np.sum(np.all(tl > 230, axis=2)) / (tl_h * tl_w) * 100

        # Check bottom-right area for white/bright region (URL bar)
        br_h, br_w = int(h * 0.07), int(w * 0.50)
        br = arr[-br_h:, -br_w:, :]
        br_white = np.sum(np.all(br > 230, axis=2)) / (br_h * br_w) * 100

        return tl_white > 40 and br_white > 30
    except Exception:
        return False


def remove_dealer_frame(img_bytes: bytes) -> bytes:
    """Remove the Automotive Avenues dealer frame by cropping.

    Previous approach used OpenCV inpainting which created ugly smeared
    artifacts (blue blobs, distorted corners).  New approach simply crops
    away the top 13% (logo + blue swoosh) and bottom 7% (URL bar).
    The result is a clean car photo with no artifacts.

    Returns cropped JPEG bytes, or original bytes if an error occurs.
    """
    from PIL import Image
    from io import BytesIO

    try:
        img = Image.open(BytesIO(img_bytes))
        w, h = img.size
        if h < 100 or w < 100:
            return img_bytes

        top_px = int(h * 0.13)   # top 13% — logo + blue swoosh
        bot_px = int(h * 0.07)   # bottom 7% — URL bar

        cropped = img.crop((0, top_px, w, h - bot_px))

        out = BytesIO()
        cropped.save(out, format="JPEG", quality=95)
        return out.getvalue()
    except Exception:
        return img_bytes
