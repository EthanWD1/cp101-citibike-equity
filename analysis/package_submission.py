"""Package only reviewed project artifacts, including the original raw data."""
from datetime import datetime, timezone
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from .download_data import checksum

ARCHIVE = Path("Group_PAIR_TrackB_midterm.zip")
DIRECTORIES = ["analysis", "data/raw", "data/processed", "docs", "notebooks", "tests", "visualizations"]
ROOT_FILES = ["README.md", ".gitignore", "requirements.txt", "requirements-dev.txt", "Group_PAIR_midterm.pdf"]


def package():
    files = [Path(name) for name in ROOT_FILES]
    for directory in DIRECTORIES:
        files.extend(p for p in Path(directory).rglob("*") if p.is_file()
                     and not any(part.startswith(".") or part == "__pycache__" for part in p.parts)
                     and p.suffix not in [".pyc", ".part", ".sqlite"])
    files = sorted(set(files))
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    required = [Path("notebooks/midterm_analysis.ipynb"), Path("data/raw/202509-citibike-tripdata.zip")]
    assert all(p in files for p in required)
    notebook = json.loads(required[0].read_text())
    assert all(cell.get("execution_count") is not None for cell in notebook["cells"] if cell["cell_type"] == "code"), "Execute the notebook before packaging"
    assert not any(output.get("output_type") == "error" for cell in notebook["cells"] for output in cell.get("outputs", []))
    manifest = {"built_at_utc": datetime.now(timezone.utc).isoformat(),
                "group": "PAIR", "track": "B", "files": {str(p): {"bytes": p.stat().st_size, "sha256": checksum(p)} for p in files}}
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zipped:
        for path in files:
            zipped.write(path, arcname=path.as_posix())
        zipped.writestr("SUBMISSION_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
    with ZipFile(ARCHIVE) as zipped:
        damaged = zipped.testzip()
        if damaged:
            raise ValueError(f"ZIP integrity failure: {damaged}")
    print(f"Created {ARCHIVE}: {ARCHIVE.stat().st_size:,} bytes, {len(files)+1} entries; CRC checks passed.")
    print(f"SHA-256: {checksum(ARCHIVE)}")
    return manifest


if __name__ == "__main__":
    package()
