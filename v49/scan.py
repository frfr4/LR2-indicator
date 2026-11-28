"""Collect chart records by content hash from the indicated public chart collections."""
from pathlib import Path
from zipfile import ZipFile, BadZipFile
from hashlib import md5
import argparse

def collect(base, repos, destination):
    with ZipFile(base) as z:
        wanted={l.split()[0].decode() for l in z.read('charts-v47.tsv').splitlines()}
    destination.mkdir(exist_ok=True)
    def save(data):
        digest=md5(data).hexdigest()
        if digest in wanted:
            (destination/(digest+'.bms')).write_bytes(data)
    chart_ext={'.bms','.bme','.bml'}
    for repo in repos:
        for file in sorted(repo.rglob('*')):
            if file.suffix.lower() in chart_ext:
                save(file.read_bytes())
            if file.suffix.lower()!='.zip':
                continue
            try:
                with ZipFile(file) as arc:
                    for row in arc.infolist():
                        if Path(row.filename).suffix.lower() in chart_ext and row.file_size<16_000_000:
                            save(arc.read(row))
            except BadZipFile:
                continue
    print(len(list(destination.glob('*.bms'))),'hash-matched catalog charts')
if __name__=='__main__':
    import sys
    collect(Path('v47/data.zip'),[Path(s) for s in sys.argv[2:]],Path(sys.argv[1]))
