"""Select only catalog-matched note files from a pinned public sabun mirror."""
from pathlib import Path
import argparse, hashlib, io, tarfile, zipfile, urllib.request, shutil
REPO='darksabun/mirror'
REV='557c1804282527109867e45b3bf78f0715c46cf8'
def main(source, destination):
    wanted={s.split()[0] for s in source.read_text().splitlines() if s.strip()}
    destination.mkdir(parents=True,exist_ok=True)
    def match(data):
        md5=hashlib.md5(data).hexdigest()
        if md5 in wanted:(destination/(md5+'.bms')).write_bytes(data)
    def chart(name):
        return name.lower().endswith(('.bms','.bme','.bml'))
    with urllib.request.urlopen(f'https://codeload.github.com/{REPO}/tar.gz/{REV}',timeout=180) as response, tarfile.open(mode='r|gz',fileobj=response) as archive:
        for f in archive:
            if not f.isfile() or f.size>8_000_000:continue
            if chart(f.name):match(archive.extractfile(f).read())
            elif f.name.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(io.BytesIO(archive.extractfile(f).read())) as nested:
                        for entry in nested.infolist():
                            if chart(entry.filename) and entry.file_size<=3_000_000:
                                match(nested.read(entry))
                except (RuntimeError,ValueError,zipfile.BadZipFile,NotImplementedError):continue
    count=len(list(destination.glob('*.bms')))
    print('Unique original chart MD5 matches:',count)
    if count==0:raise ValueError('No matched source charts')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('catalog',type=Path);ap.add_argument('out',type=Path)
    args=ap.parse_args();main(args.catalog,args.out)
