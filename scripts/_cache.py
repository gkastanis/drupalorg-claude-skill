"""Simple disk cache for drupal.org API responses.

Stores JSON responses in ~/.cache/drupal-org-api/ with a configurable TTL.
Shared across all scripts in this skill.
"""

import hashlib
import json
import os
import time
import urllib.request
import urllib.error

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "drupal-org-api")


def _cache_path(url):
    """Return the cache file path for a URL."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"{url_hash}.json")


def _read_cache(url, ttl):
    """Read a cached response if it exists and is fresh."""
    path = _cache_path(url)
    try:
        stat = os.stat(path)
        if time.time() - stat.st_mtime > ttl:
            return None
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _write_cache(url, data):
    """Write a response to the cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(url)
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


def cached_fetch_json(url, ttl=300):
    """Fetch JSON from a URL with disk caching.

    Args:
        url: The URL to fetch.
        ttl: Cache lifetime in seconds. Default 5 minutes.
             Use 0 to skip cache (always fetch fresh).

    Returns:
        Parsed JSON data, or None on error.
    """
    if ttl > 0:
        cached = _read_cache(url, ttl)
        if cached is not None:
            return cached

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            if ttl > 0:
                _write_cache(url, data)
            return data
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None
