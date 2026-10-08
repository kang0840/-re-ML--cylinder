"""Build immutable wheels from the only editable common source: root/system."""

import argparse
import base64
import csv
from email.parser import Parser
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "ML-cylinder" / "deploy"


def source_manifest(root):
    """Identify every packaged Python module and the packaging definition."""
    files = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((root / "system").rglob("*.py"))
        if "__pycache__" not in path.parts
    }
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    identity = {
        "version": config["project"]["version"],
        "files": files,
        "pyproject_sha256": hashlib.sha256(
            (root / "pyproject.toml").read_bytes()
        ).hexdigest(),
    }
    identity["source_sha256"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()
    ).hexdigest()
    return identity


def verify_wheel(wheel, root=PROJECT_ROOT):
    """Reject missing, modified or unexpected code and non-package content."""
    manifest = source_manifest(root)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        modules = {name for name in names if name.endswith(".py")}
        if modules != set(manifest["files"]):
            raise RuntimeError("Wheel module set differs from Canonical Source")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise RuntimeError(
                    "Wheel module differs from Canonical Source: " + name
                )
        for name in names:
            if not name.endswith(".py") and ".dist-info/" not in name:
                raise RuntimeError("Unexpected Wheel content: " + name)
        metadata_path = next(name for name in names if name.endswith("/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_path).decode())
        if metadata["Name"].replace("_", "-") != "smart-cylinder-common":
            raise RuntimeError("Wrong distribution name")
        if metadata["Version"] != manifest["version"]:
            raise RuntimeError("Wrong distribution version")
        prefix = metadata_path.rsplit("/", 1)[0]
        provenance = json.loads(archive.read(prefix + "/canonical-source.json"))
        if provenance != manifest:
            raise RuntimeError("Wheel provenance differs from Canonical Source")
        initializer = archive.read("system/__init__.py").decode()
        if '__version__ = "' + manifest["version"] + '"' not in initializer:
            raise RuntimeError("Package and distribution version differ")
    return manifest


def add_provenance(wheel, manifest):
    """Embed source identity and update RECORD without creating a source copy."""
    with zipfile.ZipFile(wheel) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    record = next(name for name in contents if name.endswith("/RECORD"))
    prefix = record.rsplit("/", 1)[0]
    contents[prefix + "/canonical-source.json"] = json.dumps(
        manifest, sort_keys=True, indent=2
    ).encode()
    rows = []
    for name, data in sorted(contents.items()):
        if name != record:
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(
                b"="
            )
            rows.append((name, "sha256=" + digest.decode(), str(len(data))))
    rows.append((record, "", ""))
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    contents[record] = output.getvalue().encode()
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def build():
    manifest = source_manifest(PROJECT_ROOT)
    with tempfile.TemporaryDirectory(prefix="smart-cylinder-build-") as temporary:
        staging = Path(temporary)
        shutil.copy2(PROJECT_ROOT / "pyproject.toml", staging / "pyproject.toml")
        for name in manifest["files"]:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PROJECT_ROOT / name, target)
        environment = dict(os.environ, SOURCE_DATE_EPOCH="315532800")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-cache-dir",
                "--disable-pip-version-check",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(staging / "wheel-output"),
                str(staging),
            ],
            env=environment,
            check=True,
        )
        wheels = list((staging / "wheel-output").glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("Expected exactly one Wheel")
        wheel = wheels[0]
        add_provenance(wheel, manifest)
        verify_wheel(wheel)
        destination = OUTPUT_DIR / wheel.name
        # The existing deploy directory is reused; never create another source tree.
        if not OUTPUT_DIR.is_dir():
            raise RuntimeError("Approved output directory is missing")
        if destination.exists():
            if destination.read_bytes() != wheel.read_bytes():
                raise RuntimeError(
                    "Version already exists with different content; bump version"
                )
        else:
            with destination.open("xb") as target:
                target.write(wheel.read_bytes())
        return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    wheel = args.verify if args.verify else build()
    manifest = verify_wheel(wheel)
    print("Wheel:", wheel)
    print("Version:", manifest["version"])
    print("SHA-256:", hashlib.sha256(wheel.read_bytes()).hexdigest())
    print("Canonical Source SHA-256:", manifest["source_sha256"])
    print("Canonical Python modules:", len(manifest["files"]))


if __name__ == "__main__":
    main()
