"""Reduce the public LR2IR archive to anonymous lamp observations on the requested charts."""
import sqlite3,csv,random
from pathlib import Path
from array import array
import numpy as np
p=Path('ir-data');p.mkdir(exist_ok=True)
db=sqlite3.connect('file:lr2ir.db?mode=ro',uri=True)
hashes=Path('v38-ir/md5.txt').read_text().split();uf=array('I'); ch=array('H'); lamp=array('B');levels={};uids={}
out=(p/'totals.csv').open('w',newline='');wr=csv.writer(out);wr.writerow(['md5','people','plays','failed','easy','normal','hard','fc'])
for i,h in enumerate(hashes):
    item=db.execute('select play_people,play_count,failed_count,easy_count,normal_count,hard_count,fc_count from chart where md5=?',(h,)).fetchone()
    if item:wr.writerow([h,*item])
    for u,l in db.execute('select player_id,clear_type from pb where md5=? and is_cheated=0',(h,)):
        ix=uids.setdefault(u,len(uids));lc=levels.setdefault(l,len(levels));uf.append(ix);ch.append(i);lamp.append(lc)
out.close()
# Ordinals are randomized and the key mapping is discarded. No player identifiers leave the runner.
rng=np.random.default_rng(38412);alias=rng.permutation(len(uids)).astype(np.int32)
np.savez_compressed(p/'observations.npz',u=alias[np.frombuffer(uf,np.uint32)],i=np.frombuffer(ch,np.uint16),lamp=np.frombuffer(lamp,np.uint8),
                    order=np.array(list(levels)),md5=np.array(hashes))
print('Requested',len(hashes),'PBs',len(ch),'anonymous players',len(uids),'lamps',list(levels))
