from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse

PLACEHOLDER = "https://YOUR-DOMAIN.example.com"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an OpenAPI schema with the deployed API base URL."
    )
    parser.add_argument("base_url", help="Public HTTPS URL, for example https://example.onrender.com")
    parser.add_argument(
        "--output",
        default="build/openapi.deployed.yaml",
        help="Output path (default: build/openapi.deployed.yaml)",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("base_url must be a valid public HTTPS URL")

    source = Path("config/openapi.yaml")
    output = Path(args.output)
    content = source.read_text(encoding="utf-8")
    if PLACEHOLDER not in content:
        raise SystemExit(f"Placeholder {PLACEHOLDER!r} was not found in {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content.replace(PLACEHOLDER, base_url), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
