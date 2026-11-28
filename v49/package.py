"""Materialize v49 resources inside a complete, staged Windows build."""
from pathlib import Path
import base64
import csv
import gzip
import hashlib
import json
import shutil
import sys
import tempfile
from decimal import Decimal
from PIL import Image

HERE=Path(__file__).resolve().parent
RADAR='LR2files/Theme/KCOOL_WMIX_FHD/WMIX/select/radar'
MODEL='8269c811d5fe331566baaa93c1f43baf'
GAME='aaffdf6c3fd3731cfb577b9375381c57'
def rows(path):
    return dict(line.split('\t',1) for line in path.read_text(encoding='ascii').splitlines())

def patch_lamps(folder, v48):
    sys.path.insert(0,str(v48.resolve()))
    from package_windows import load_frozen, patch, digest
    manifest=json.loads((v48/'manifest.json').read_text(encoding='utf-8'))
    raw=gzip.decompress(base64.b64decode(''.join((v48/name).read_text().strip() for name in manifest['frozen_chunks'])))
    assert digest(raw)==manifest['frozen_sha256']
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'frozen.csv'
        p.write_bytes(raw)
        with p.open(encoding='utf-8-sig') as f:
            ids={r['md5'] for r in csv.DictReader(f)}
        estimates=load_frozen(p,ids)
    for path,expected in manifest['updated_table_sha256'].items():
        p=folder/Path(path).name
        result,_=patch(p.name,p.read_bytes(),estimates)
        assert digest(result)==expected
        p.write_bytes(result)
    grades=rows(folder/'tiers.tsv')
    summaries=rows(folder/'selection-v47.tsv')
    clear=folder/'clear-v43.tsv'
    revised=[]
    special={h for h,g in grades.items() if g=='59'}
    assert len(special)==4 and MODEL in special
    for line in clear.read_bytes().splitlines(keepends=True):
        cells=line.rstrip(b'\n\r').decode('ascii').split('\t')
        if cells[0] in special:
            assert cells[1]==cells[3]=='.'
            physical=summaries[cells[0]].split('\t')
            for j,src in ((2,2),(4,3)):
                cells[j]=str(int(Decimal(physical[src])*100))
            line='\t'.join(cells).encode()+line[len(line.rstrip(b'\n\r')):]
        revised.append(line)
    clear.write_bytes(b''.join(revised))
    cb=rows(clear)
    assert cb[MODEL]=='.\t2911\t.\t3053'
    assert cb[GAME].split('\t')[::2]==['519','959']
    assert len(cb)==len(summaries)==6226

def append_grade(folder,name,height,prefix,digit,edge):
    path=folder/name
    sheet=Image.open(path).convert('RGBA')
    new=Image.new('RGBA',(sheet.width,sheet.height+height))
    new.paste(sheet)
    new.paste(sheet.crop((0,height*prefix,edge,height*(prefix+1))),(0,sheet.height))
    new.paste(sheet.crop((edge,height*digit,sheet.width,height*(digit+1))),(edge,sheet.height))
    new.save(path,optimize=True)

def run(stage,v48):
    dest=stage/RADAR
    for name in ('song-v43.png','player-v43.png'):
        p=dest/name
        atlas=Image.open(p).convert('RGBA')
        atlas.paste((0,0,0,0),(415,81,473,100))
        atlas.alpha_composite(Image.open(HERE/'axis.png').convert('RGBA'),(421,82))
        atlas.paste(Image.open(HERE/'table.png').convert('RGBA'),(147,622))
        atlas.save(p,optimize=True)
    append_grade(dest,'tiers.png',26,25,7,53)
    append_grade(dest,'shadows.png',32,26,8,56)
    p=dest/'tiers.tsv'
    table=rows(p)
    table.update(rows(HERE/'tier-updates.tsv'))
    assert table[MODEL]=='59' and table[GAME]=='5'
    p.write_bytes(''.join(f'{k}\t{table[k]}\n' for k in sorted(table)).encode('ascii'))
    patch_lamps(dest,v48)
    shutil.copyfile(HERE/'charts-v49.tsv',dest/'charts-v49.tsv')
    shutil.copyfile(HERE/'인수인계.TXT',stage/'인수인계.TXT')
if __name__=='__main__':
    run(Path(sys.argv[1]),Path(sys.argv[2]))
