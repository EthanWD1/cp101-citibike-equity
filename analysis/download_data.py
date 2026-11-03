"""Download unchanged source files; reruns verify existing files against the manifest."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone

from .config import RAW, SOURCES


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = RAW / "sources.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest = dict(old)
    for name, url in SOURCES.items():
        path = RAW / name
        if not path.exists():
            part = path.with_suffix(path.suffix + ".part")
            print(f"Downloading {name}", flush=True)
            # curl uses the operating system's certificate store on macOS; never disable TLS.
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                            "--retry", "3", "--connect-timeout", "30", "--continue-at", "-",
                            "--output", str(part), url], check=True)
            part.replace(path)
        digest = checksum(path)
        if name in old and old[name]["sha256"] != digest:
            raise ValueError(f"Source checksum changed: {name}; investigate before updating provenance")
        manifest[name] = old.get(name, {
            "url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "bytes": path.stat().st_size, "sha256": digest,
        })
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Verified {name}: {path.stat().st_size:,} bytes", flush=True)
    return manifest


if __name__ == "__main__":
    download()
