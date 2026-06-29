#!/usr/bin/env python3
"""Extract PUB India challenge data from zip into data/ directory."""

import argparse
import zipfile
from pathlib import Path

ZIP_NAME = "[PUB] India_runs_data_and_ai_challenge.zip"
BUNDLE = "[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge"

FILES = [
    "sample_candidates.json",
    "candidate_schema.json",
    "candidates.jsonl",
    "validate_submission.py",
    "sample_submission.csv",
    "submission_metadata_template.yaml",
]


def extract(root: Path, files: list[str] | None = None) -> None:
    zip_path = root / ZIP_NAME
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if not zip_path.exists():
        raise FileNotFoundError(f"Zip not found: {zip_path}")

    targets = files or FILES
    with zipfile.ZipFile(zip_path) as zf:
        for name in targets:
            src = f"{BUNDLE}/{name}"
            dest = data_dir / name if name != "validate_submission.py" else root / name
            if src not in zf.namelist():
                print(f"Skip (not in zip): {name}")
                continue
            print(f"Extracting {name} -> {dest}")
            if name == "candidates.jsonl":
                with zf.open(src) as src_f, open(dest, "wb") as dst_f:
                    while chunk := src_f.read(8 * 1024 * 1024):
                        dst_f.write(chunk)
            else:
                dest.write_bytes(zf.read(src))

    # Extract job description text from docx if missing
    jd_txt = data_dir / "job_description.txt"
    if not jd_txt.exists():
        import xml.etree.ElementTree as ET
        docx_src = f"{BUNDLE}/job_description.docx"
        with zipfile.ZipFile(zip_path) as zf:
            xml = zf.read(docx_src)
        root_xml = ET.fromstring(xml)
        texts = [
            t.text for t in root_xml.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            ) if t.text
        ]
        jd_txt.write_text("\n".join(texts), encoding="utf-8")
        print(f"Extracted job_description.txt")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--files", nargs="*", help="Specific files to extract")
    args = parser.parse_args()
    extract(Path(args.root).resolve(), args.files)
