"""Check both shipped SP chart tables against the independent 6,226-MD5 clearing catalog."""
import hashlib
import math
import re
import sys
import zipfile
from pathlib import Path

names = {"charts-v47.tsv": 13, "selection-v47.tsv": 7}


def check_rows(lines, columns):
    records = set()
    for line_no, line in enumerate(lines.splitlines(), 1):
        values = line.split()
        if len(values) != columns:
            raise ValueError(f"incorrect column count on line {line_no}")
        md5, *numbers = values
        if not re.fullmatch(r"[0-9a-f]{32}", md5) or md5 in records:
            raise ValueError(f"invalid/duplicate MD5 on line {line_no}")
        if not all(math.isfinite(float(n)) for n in numbers):
            raise ValueError(f"non-finite number on line {line_no}")
        records.add(md5)
    return records


def verify(archive, clears, destination):
    reference = {line.split()[0] for line in clears.read_text(encoding="utf-8-sig").splitlines()}
    if len(reference) != 6226:
        raise ValueError(f"reference chart count {len(reference)}")
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist()) != len(names) or set(z.namelist()) != set(names):
            raise ValueError(f"unexpected archive entries {z.namelist()}")
        destination.mkdir(parents=True, exist_ok=True)
        for name, columns in names.items():
            data = z.read(name)
            rows = check_rows(data.decode("utf-8-sig"), columns)
            if rows != reference:
                raise ValueError(f"{name} chart set differs from reference by {len(rows ^ reference)} keys")
            (destination / name).write_bytes(data)
            print(f"{name} checked {len(rows)} unique charts; SHA256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    verify(*(Path(path) for path in sys.argv[1:]))
