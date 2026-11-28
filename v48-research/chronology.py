"""Read historical timestamps and select anonymized fixed-date subsets on the runner.

This script writes private job-temporary observations. The upload step receives
only chart-level aggregated fits with a minimum count of five.
"""
from pathlib import Path
import csv,gzip,hashlib,json,re,sqlite3,sys
from array import array
from collections import Counter
from urllib.request import urlopen,Request
import numpy as np

root=Path('private/v47')
scorefile=Path(sys.argv[1]).resolve();fmt=root/'base/catalog.tsv'
with fmt.open() as f: catalog=[r['md5'] for r in csv.DictReader(f,delimiter='\t')]
db=sqlite3.connect(f'file:{scorefile}?mode=ro&immutable=1',uri=True)
db.execute('CREATE TEMP TABLE selected(hash TEXT PRIMARY KEY, chart INTEGER)')
db.executemany('INSERT INTO selected VALUES (?,?)',enumerate([]))
db.executemany('INSERT INTO selected VALUES (?,?)',[(h,k) for k,h in enumerate(catalog)])
policy=Path('.github/workflows/v43-lamp-inputs.yml').read_text();m=re.search(r's\.playerid not in \(([0-9, ]+)\)',policy)
assert m, 'historical eligibility source missing';skip=[int(v) for v in m[1].split(',')]
qmarks=','.join('?' for _ in skip)
sql=f'SELECT s.playerid,k.chart,s.clear,s.lastupdate FROM scores s CROSS JOIN selected k ON k.hash=s.hash WHERE s.clear BETWEEN 1 AND 6 AND s.notes>0 AND s.playerid>0 AND s.playerid NOT IN ({qmarks})'
# Temporary pseudonyms and timestamp flags remain on the runner only.
su=array('i');it=array('H');lamps=array('B');dates=array('q');people={}
for p,i,L,t in db.execute(sql,skip):
    su.append(people.setdefault(p,len(people)));it.append(i);lamps.append(min(5,L));dates.append(int(t or 0))
u=np.frombuffer(su,dtype='int32');i=np.frombuffer(it,dtype='uint16');l=np.frombuffer(lamps,dtype='uint8');raw=np.frombuffer(dates,dtype='int64')
# Scores expose Unix seconds. Accept milliseconds only after a calendar-range check.
t=np.where((raw>=1000000000000)&(raw<1900000000000),raw//1000,raw)
valid=(t>=950000000)&(t<1900000000)
safe=Path('aggregates');safe.mkdir(exist_ok=True)
metadata={'charts':len(catalog),'rows':len(u),'people':len(people),'unknown_or_outside_date':int((~valid).sum()),
          'timestamp_ranges_count':{str(k):int(v) for k,v in Counter(np.floor(np.log10(np.maximum(1,raw))).astype(int)+1).items()},
          'source':'MellDa1024/lr2ir-getplayerxml @ aa3a8881c6e1d7c58ff3a68d34f7f50ff7a1124f'}
if not valid.any():raise RuntimeError('No recognized date. Only aggregate diagnostics available: '+json.dumps(metadata))
roster=set()
try:
    payload=urlopen(Request('https://web.archive.org/web/20200311132835id_/http://walkure.net/hakkyou/data/player.json',headers={'User-Agent':'OpenLR2 historical score research'}),timeout=25).read(8<<20)
    if payload[:2]==b'\x1f\x8b':payload=gzip.decompress(payload)
    if hashlib.sha256(payload).hexdigest()!='725c9c509195c47654c4b86f02ab30552b9bd6a5f7911732b9040972e01ceae0':raise ValueError('roster checksum')
    roster={int(r[0]) for r in json.loads(payload)}
    assert len(roster)==28118
    metadata['roster']='2020-03-11 archived public ranking, 28118 members'
except Exception as exc:metadata['roster_unavailable']=type(exc).__name__
matched=np.zeros(len(people),dtype=bool)
for p,j in people.items():matched[j]=p in roster
selections={'oct2018':valid&(t<=1540724400),'may2019':valid&(t<=1557137719),'jan2018':valid&(t<=1514764800)}
if roster:
    selections['roster_oct2018']=selections['oct2018']&matched[u];selections['roster_final']=matched[u]
for name,mask in selections.items():
    private=Path('private')/name;private.mkdir(parents=True,exist_ok=True)
    people_sub,v=np.unique(u[mask],return_inverse=True)
    np.savez_compressed(private/'obs.npz',md5=np.array(catalog),u=v.astype('int32'),i=i[mask],lamp=l[mask])
    metadata[name]={'records':int(mask.sum()),'people':len(people_sub)}
    H=np.bincount(i[mask].astype('int64')*5+l[mask]-1,minlength=len(catalog)*5).reshape(-1,5)
    with (safe/(name+'_totals.csv')).open('w') as fp:
        w=csv.writer(fp);w.writerow(['md5','people','FAILED','EASY','NORMAL','HARD','FC'])
        for h,hs in zip(catalog,H):w.writerow([h,hs.sum(),*(hs if hs.sum()>=5 else ['']*5)])
(safe/'coverage.json').write_text(json.dumps(metadata,indent=2))
print(json.dumps(metadata,indent=2))
