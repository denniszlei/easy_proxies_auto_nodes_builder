#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

SUBSCRIPTION_URL = "https://imtaqin.id/api/vpn/sub/all"
PROXIES_URL = "https://imtaqin.id/api/proxies"
REQUEST_HEADERS = {
    "User-Agent": "clash-verge/v2.2.3",
    "Accept": "*/*",
}
SUPPORTED_SCHEMES = {
    "vmess",
    "vless",
    "trojan",
    "ss",
    "hysteria2",
    "hy2",
    "tuic",
    "anytls",
    "socks5",
    "socks",
    "http",
    "https",
}
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DIST_DIR = REPO_ROOT / "dist"
NODE_FILE = DIST_DIR / "node.txt"
METADATA_FILE = DIST_DIR / "metadata.json"
TIMEOUT = 30


@dataclass(frozen=True)
class CandidateNode:
    uri: str
    source_kind: str
    scheme: str
    country: str
    host: str
    port: int


class BuildError(RuntimeError):
    pass


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8", errors="replace")


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url))


def normalize_uri(raw: str) -> str | None:
    line = raw.strip()
    if not line or line.startswith("#"):
        return None
    scheme = line.split("://", 1)[0].lower() if "://" in line else ""
    if scheme not in SUPPORTED_SCHEMES:
        return None
    return line


def parse_host_port(uri: str) -> tuple[str, int]:
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    port = parsed.port or 0
    return host, port


def make_candidate(uri: str, source_kind: str, country: str = "ZZ") -> CandidateNode | None:
    scheme = uri.split("://", 1)[0].lower()
    if scheme not in SUPPORTED_SCHEMES:
        return None
    host, port = parse_host_port(uri)
    return CandidateNode(
        uri=uri,
        source_kind=source_kind,
        scheme=scheme,
        country=(country or "ZZ").upper(),
        host=host,
        port=port,
    )


def parse_subscription_nodes(text: str) -> list[CandidateNode]:
    nodes: list[CandidateNode] = []
    for line in text.splitlines():
        uri = normalize_uri(line)
        if uri is None:
            continue
        candidate = make_candidate(uri, source_kind="subscription")
        if candidate is not None:
            nodes.append(candidate)
    return nodes


def proxy_name(protocol: str, country: str, city: str, source: str, ip: str, port: int) -> str:
    country_part = (country or "ZZ").upper()
    city_part = city or "Unknown"
    return f"{protocol.upper()}-{country_part}-{city_part}-{source}-{ip}-{port}"


def convert_proxy_record(record: dict) -> CandidateNode | None:
    protocol = str(record.get("protocol", "")).upper()
    ip = str(record.get("ip", "")).strip()
    port_value = record.get("port")
    if not ip or port_value in (None, ""):
        return None
    try:
        port = int(port_value)
    except (TypeError, ValueError):
        return None
    if port <= 0 or port > 65535:
        return None

    country = str(record.get("country") or "ZZ").upper()
    city = str(record.get("city") or "Unknown").strip() or "Unknown"
    source = str(record.get("source") or "imtaqin").strip() or "imtaqin"
    name = quote(proxy_name(protocol, country, city, source, ip, port), safe="")

    if protocol == "SOCKS5":
        uri = f"socks5://{ip}:{port}#{name}"
        return make_candidate(uri, source_kind="json", country=country)
    if protocol == "HTTP":
        uri = f"http://{ip}:{port}#{name}"
        return make_candidate(uri, source_kind="json", country=country)
    return None


def parse_json_proxy_nodes(payload: dict) -> tuple[list[CandidateNode], str | None]:
    proxies = payload.get("proxies")
    if not isinstance(proxies, list):
        raise BuildError("JSON proxy API returned unexpected payload: missing proxies list")
    nodes: list[CandidateNode] = []
    for record in proxies:
        if not isinstance(record, dict):
            continue
        candidate = convert_proxy_record(record)
        if candidate is not None:
            nodes.append(candidate)
    updated = payload.get("updated")
    return nodes, str(updated) if updated else None


def dedupe_nodes(nodes: Iterable[CandidateNode]) -> list[CandidateNode]:
    chosen_by_uri: dict[str, CandidateNode] = {}
    json_seen_by_endpoint: set[tuple[str, str, int]] = set()

    for node in nodes:
        existing = chosen_by_uri.get(node.uri)
        if existing is not None:
            if existing.source_kind == "json" and node.source_kind == "subscription":
                chosen_by_uri[node.uri] = node
            continue

        endpoint_key = (node.scheme, node.host, node.port)
        if node.source_kind == "json":
            if endpoint_key in json_seen_by_endpoint:
                continue
            json_seen_by_endpoint.add(endpoint_key)

        chosen_by_uri[node.uri] = node

    return sorted(
        chosen_by_uri.values(),
        key=lambda item: (item.scheme, item.country, item.host, item.port, item.uri),
    )


def write_outputs(nodes: list[CandidateNode], proxy_updated: str | None) -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    NODE_FILE.write_text("".join(f"{node.uri}\n" for node in nodes), encoding="utf-8")

    counts = Counter(node.scheme for node in nodes)
    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "subscription": SUBSCRIPTION_URL,
            "json": PROXIES_URL,
            "json_updated": proxy_updated,
        },
        "node_count": len(nodes),
        "protocol_counts": dict(sorted(counts.items())),
        "artifact": str(NODE_FILE.relative_to(REPO_ROOT)),
    }
    METADATA_FILE.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    try:
        subscription_text = fetch_text(SUBSCRIPTION_URL)
        proxy_payload = fetch_json(PROXIES_URL)

        subscription_nodes = parse_subscription_nodes(subscription_text)
        json_nodes, proxy_updated = parse_json_proxy_nodes(proxy_payload)
        nodes = dedupe_nodes([*subscription_nodes, *json_nodes])

        if not nodes:
            raise BuildError("No compatible nodes were generated")

        write_outputs(nodes, proxy_updated)
        print(f"Generated {len(nodes)} nodes -> {NODE_FILE}")
        return 0
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, BuildError) as exc:
        print(f"build_nodes failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
