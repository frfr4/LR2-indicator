"""Read the documented v3 snapshot in place. Write only chart-level summaries."""
import csv
import gzip
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np

TAG_RULES = {
    'scratch': r'スクラッチ|連皿|着地|皿複合|サラ|連スク',
    'jack': r'縦連|縦れん|縦レン|歯抜け|連打',
    'delay': r'ズレ|ずれ|ディレイ',
    'end': r'ラス殺|ラスト殺|ラスト難|後殺|終盤難',
    'recovery': r'回復|ウィニングラン|ウイニングラン',
    'speed': r'ソフラン|速度変化|低速|変速',
    'hand': r'片手|無理押|運指|ガチ押|割れ|外れ|ハズレ|軸',
    'density': r'高密度|発狂|物量',
}
TAGS = {key:re.compile(expr) for key,expr in TAG_RULES.items()}
LEVELS = {'FAILED','EASY CLEAR','CLEAR','HARD CLEAR','FULLCOMBO','FULL COMBO','NO PLAY','EASY','HARD','NORMAL'}
SOURCE = 'https://github.com/zkldi/lr2ir-dataset'
SHA256 = 'b8b94d9c67cf94411a71501c3533bd15877bd727fd687c060749fae29267b5cf'
BUCKETS = 20
PER_CHART = 96

def parse_args():
    dbp, catalog, out = map(Path, sys.argv[1:4])
    db = sqlite3.connect(f'file:{dbp.resolve()}?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA cache_size=-320000')
    md5s = sorted({line.split('\t')[0] for line in catalog.read_text().splitlines()})
    assert len(md5s) == 6226 and all(re.fullmatch(r'[0-9a-f]{32}',s) for s in md5s)
    return db,md5s,out

def probe(blob):
    if blob.startswith(b'\x1f\x8b'):
        try:
            blob=gzip.decompress(blob)
        except (OSError,EOFError):
            return 'broken_gzip'
        return 'gzip_'+classify(blob)
    return classify(blob)

def classify(blob):
    if not blob: return 'empty'
    if blob.startswith(b'<?xml'): return 'xml'
    parts=blob.strip().split(b',')
    if len(parts)>1:
        return 'csv_fields_'+str(min(20,len(parts)))+'_printable_'+str(all(32<=b<127 for b in parts[-1][:100]))
    if re.match(rb'^[A-Za-z0-9@+/_=\x20-\x7e]+$', blob):
        return 'printable_direct'
    if blob[:1]==b'\x78':return 'possible_zlib'
    return 'other_binary'

def replay_sample(db, md5):
    # Sample evenly across the PB score ranking, not at its first 96 rows.
    sql="""SELECT p.rank,p.score_max,p.combo_max,p.pgreat,p.great,p.good,p.bad,p.poor,
                  g.ghost FROM ghost g JOIN pb p ON p.md5=g.md5 AND p.player_id=g.player_id
           WHERE g.md5=? AND p.is_cheated=0 ORDER BY p.rank"""
    total=db.execute('SELECT count(*) FROM ghost WHERE md5=?',(md5,)).fetchone()[0]
    if total==0:return total,[]
    # Sort compact keys first; fetching all blob bytes would read far more than the sample.
    keys=db.execute("""SELECT g.player_id FROM ghost g JOIN pb p ON p.md5=g.md5 AND p.player_id=g.player_id
                       WHERE g.md5=? AND p.is_cheated=0 ORDER BY p.rank""",(md5,)).fetchall()
    if not keys:return total,[]
    chosen=np.unique(np.rint(np.linspace(0,len(keys)-1,min(PER_CHART,len(keys)))).astype(int))
    single=sql.replace(' AND p.is_cheated=0 ORDER BY p.rank',' AND g.player_id=? AND p.is_cheated=0')
    return total,[db.execute(single,(md5,keys[pos][0])).fetchone() for pos in chosen]

def scan():
    db,md5s,out=parse_args()
    out.mkdir(parents=True,exist_ok=True)
    try:
        from ghost_decode import decode
    except ImportError:
        decode=None
    rows=[]; bins=[];hist=Counter();failures=Counter()
    meta=['play_count','play_people','clear_count','clear_people','fc_count','hard_count','normal_count','easy_count','failed_count']
    for i,md5 in enumerate(md5s):
        row={'md5':md5}
        ch=db.execute('SELECT '+','.join(meta)+',comment,'+','.join('tag_'+str(n) for n in range(1,11))+' FROM chart WHERE md5=?',(md5,)).fetchone()
        row['chart_found']=int(ch is not None)
        for k,name in enumerate(meta):row['archive_'+name]=None if ch is None else ch[k]
        desc=' '.join(str(v) for v in ch[len(meta):] if v) if ch else ''
        for name,regex in TAGS.items():row['chart_tag_'+name]=int(bool(regex.search(desc)))
        pb=db.execute("""SELECT count(*),sum(CASE WHEN trim(note)!='' THEN 1 ELSE 0 END),
            avg(CASE WHEN combo_max>0 THEN CAST(bad_poor AS REAL)/combo_max END),
            avg(CASE WHEN combo_max>0 THEN CAST(combo AS REAL)/combo_max END),
            avg(CASE WHEN score_max>0 THEN CAST(score AS REAL)/score_max END)
            FROM pb WHERE md5=? AND is_cheated=0""",(md5,)).fetchone()
        for k,v in zip(['pb_rows','pb_note_nonempty','pb_mean_bp_per_note','pb_mean_combo_ratio','pb_mean_score_ratio'],pb):row[k]=v
        comments=Counter()
        for (note,) in db.execute("SELECT note FROM pb WHERE md5=? AND is_cheated=0 AND length(trim(note))>0",(md5,)):
            for name,regex in TAGS.items():
                if regex.search(note):comments[name]+=1
        for name in TAGS:row['pb_mentions_'+name]=comments[name]
        total,samples=replay_sample(db,md5)
        row.update(archived_ghosts=total,ghosts_sampled=len(samples),decoded=0,exact_pb_match=0)
        sums=np.zeros((BUCKETS,3),dtype=np.int64)
        for rank,scoremax,combo_max,pg,gr,gd,bad,poor,blob in samples:
            hist[probe(blob)]+=1
            if decode is None:continue
            try:
                judges,empty=decode(blob)
                if not judges or any(n<1 or n>5 for n in judges):raise ValueError('invalid returned judgement')
            except (ValueError,TypeError,OverflowError) as exc:
                failures[type(exc).__name__]+=1
                continue
            row['decoded']+=1
            observed=np.bincount(np.frombuffer(judges,dtype='u1'),minlength=6)
            # Require independent, exact PB tally plus a full chart before any location inference.
            if (observed[5],observed[4],observed[3],observed[2],observed[1]+empty)!=(pg,gr,gd,bad,poor) or len(judges)!=combo_max:
                continue
            row['exact_pb_match']+=1
            seq=np.frombuffer(judges,dtype='u1')
            for b,group in enumerate(np.array_split(seq,BUCKETS)):
                sums[b]+=(len(group),np.count_nonzero(group<=2),np.count_nonzero(group==3))
        if row['exact_pb_match']>=3:
            for b,values in enumerate(sums):
                bins.append((md5,b,row['exact_pb_match'],*values.tolist()))
        rows.append(row)
        if i%400==0:print('charts',i,'found',sum(x['chart_found'] for x in rows),'sampled',sum(hist.values()),flush=True)
    with (out/'archive_chart_evidence.csv').open('w',newline='') as dest:
        w=csv.DictWriter(dest,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (out/'ghost_order_bins.csv').open('w',newline='') as dest:
        w=csv.writer(dest);w.writerow(['md5','relative_judgement_order_bin','verified_replays','judged_notes','bad_or_missed','good']);w.writerows(bins)
    info={'source':SOURCE,'sha256_gzip':SHA256,'dataset_meta':db.execute('SELECT * FROM meta').fetchall(),'catalog':len(md5s),'chart_rows':sum(r['chart_found'] for r in rows),'pb_rows':sum(r['pb_rows'] or 0 for r in rows),'archived_ghosts':sum(r['archived_ghosts'] for r in rows),'sampled':sum(hist.values()),'forms':dict(hist),'decode_available':bool(decode),'decoded':sum(r['decoded'] for r in rows),'exact_pb_match':sum(r['exact_pb_match'] for r in rows),'charts_with_3_verified':len(bins)//BUCKETS,'decode_errors':dict(failures)}
    (out/'coverage.json').write_text(json.dumps(info,indent=2))
    print(info)

if __name__=='__main__':scan()
