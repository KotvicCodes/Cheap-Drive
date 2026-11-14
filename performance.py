"""Compressed official SDK transport and credential-free latency measurements."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import gzip
import http.client
import json
import statistics
import time
from urllib.parse import urlsplit

from spread import Client


class PracticeClient(Client):
    """Keep SDK validation, retry and rate limits; compress responses and time calls.

    Use one client per process. Only the public, immutable map is cached; world
    state, rosters, scores and mutation results always come from the server.
    """

    def __init__(self, *args, compression=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.compression = compression
        self._map_cache = None
        self._stats = Counter()
        self._routes = Counter()
        self._limits = {}

    def _send(self, method, path, payload, headers):
        if self.compression:
            headers = {**headers, "Accept-Encoding": "gzip"}
        started = time.perf_counter()
        try:
            status, answer, data = super()._send(method, path, payload, headers)
            self._stats["requests"] += 1
            self._stats["wire_bytes"] += len(data)
            self._stats["rate_limit_responses"] += int(status == 429)
            policy = answer.get("RateLimit-Policy")
            if policy and answer.get("RateLimit-Limit"):
                bucket = policy.split(";", 1)[0].strip('"')
                if bucket in ("practice", "final-actions", "final-reads"):
                    self._limits[bucket] = float(answer["RateLimit-Limit"])
            if answer.get("Content-Encoding", "").lower() == "gzip":
                data = gzip.decompress(data)
            self._stats["decoded_bytes"] += len(data)
            return status, answer, data
        finally:
            self._stats["transport_seconds"] += time.perf_counter() - started

    def call(self, method, path, body=None, actions=0):
        # Store endpoint categories, never keys, payloads, query strings or errors.
        parts = path.split("?", 1)[0].split("/")
        route = "/".join(parts[:3] + ([":world"] + parts[4:] if len(parts) > 3 and parts[2] == "worlds" else parts[3:]))
        self._routes[f"{method} {route}"] += 1
        started = time.perf_counter()
        try:
            return super().call(method, path, body, actions)
        finally:
            self._stats["api_seconds"] += time.perf_counter() - started

    def map(self):
        if self._map_cache is None:
            self._map_cache = super().map()
        return deepcopy(self._map_cache)

    def timing(self):
        return {**dict(self._stats), "routes": dict(self._routes),
                "rate_limits": dict(self._limits), "compression": self.compression}

    def reset_timing(self):
        self._stats.clear()
        self._routes.clear()


def benchmark(url, samples):
    """Alternate uncompressed/compressed public reads; no key or world needed."""
    parts = urlsplit(url.rstrip("/"))
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("use an HTTP(S) server URL without credentials or query parameters")
    kind = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = kind(parts.netloc, timeout=20)
    rows = []
    try:
        # Warm up the same persistent connection; omit DNS/TCP/TLS from samples.
        for index in range(samples + 1):
            for encoding in ("identity", "gzip") if index % 2 == 0 else ("gzip", "identity"):
                started = time.perf_counter()
                connection.request("GET", parts.path.rstrip("/") + "/v1/map",
                                   headers={"Accept-Encoding": encoding})
                response = connection.getresponse()
                data = response.read()
                elapsed = time.perf_counter() - started
                if response.status != 200:
                    raise RuntimeError(f"public map returned HTTP {response.status}")
                decoded = gzip.decompress(data) if response.getheader("Content-Encoding") == "gzip" else data
                json.loads(decoded)
                if index:
                    rows.append({"encoding": encoding, "seconds": elapsed,
                                 "wire_bytes": len(data), "decoded_bytes": len(decoded)})
    finally:
        connection.close()
    summary = {}
    for encoding in ("identity", "gzip"):
        group = [row for row in rows if row["encoding"] == encoding]
        summary[encoding] = {"median_seconds": statistics.median(row["seconds"] for row in group),
                             "median_wire_bytes": statistics.median(row["wire_bytes"] for row in group)}
    return {"server": url, "samples_per_encoding": samples, "summary": summary, "samples": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="https://spread.bahnexpress.com")
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 100:
        parser.error("samples must be between 1 and 100")
    try:
        print(json.dumps(benchmark(args.server, args.samples), indent=2))
        return 0
    except Exception:
        print("Benchmark failed; check the server URL and connection.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
