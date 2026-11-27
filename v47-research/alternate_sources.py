"""Aggregate independent archive fields and check the documented chart API safely, with bounded requests."""
import argparse,csv,json,re,sqlite3,time
import urllib.request,urllib.error
from pathlib import Path
from collections import Counter
import numpy as np
from ghost_decode import decode
from replay_aggregate import BUCKETS

def xml_archive(dbp,ids,out):
    db=sqlite3.connect(f"file:{dbp.resolve()}?mode=ro&immutable=1",uri=True)
    cols={r[1] for r in db.execute("pragma table_info(scores)")}
    assert {'hash','clear','notes','playerid'}<=cols
    db.execute('create temp table selected(hash text primary key) without rowid')
    db.executemany('insert into selected values (?)',[(v,) for v in ids])
    # Use the exact historical eligibility rule without duplicating its account list.
    policy=Path('.github/workflows/v43-lamp-inputs.yml').read_text()
    matched=re.search(r's\.playerid not in \(([0-9, ]+)\)', policy)
    if not matched:raise ValueError('missing frozen eligibility filter')
    exclusions=[int(x) for x in matched[1].split(',')]
    placeholders=','.join('?' for _ in exclusions)
    rule=f's.clear between 1 and 6 and s.notes>0 and s.playerid>0 and s.playerid not in ({placeholders})'
    # No identities, comments, or high-score replay records are exported.
    names=['players','failed_best','easy_best','normal_best','hard_best','fc_best']
    agg=['count(*)']+[f'sum(s.clear={n})' for n in (1,2,3,4)]+['sum(s.clear>=5)']
    field={c.casefold():c for c in cols}
    for aliases,kind in [(('playcount','play_count','playcnt'),'reported_plays'),(('clearcount','clear_count','clearcnt'),'reported_clears'),(('maxcombo','combo','max_combo'),'best_combo_fraction'),(('minbp','bp','badpoor','misscount'),'best_bp_per_note'),(('score','exscore'),'best_ex_fraction'),(('pg','pgreat','perfect'),'pgreat_fraction'),(('gr','great'),'great_fraction'),(('gd','good'),'good_fraction'),(('bd','bad'),'bad_per_note'),(('pr','poor'),'poor_per_note')]:
        actual=next((field[k] for k in aliases if k in field),None)
        if actual:
            x=f's."{actual}"'
            agg.append(f'sum({x})' if kind.startswith('reported') else f'avg(CASE WHEN {x}>=0 THEN 1.0*{x}/s.notes/{2 if kind=="best_ex_fraction" else 1} END)')
            names.append(kind)
    db.commit()
    data=db.execute(f"select s.hash,{','.join(agg)} from scores s cross join selected a on a.hash=s.hash where {rule} group by s.hash", exclusions).fetchall()
    with (out/'independent_xml_by_chart.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['md5',*names]);w.writerows(data)
    return {'schema':sorted(cols),'source':'MellDa1024/lr2ir-getplayerxml','source_commit':'aa3a8881c6e1d7c58ff3a68d34f7f50ff7a1124f','sha256_compressed':'91483d5e4e2e91945a073e87d5e4fe13a17300399f0a588b061df33fedf32621','rows':sum(r[1] for r in data),'charts':len(data)}

def public_web(ids,out):
    # One record per requested page, at a low request rate. Stop on a denial or rate limit.
    api='https://lr2ir.com'
    def get(path):
        time.sleep(.25)
        r=urllib.request.urlopen(urllib.request.Request(api+path,headers={'User-Agent':'OpenLR2 chart difficulty research/1.0'}),timeout=12)
        return r.read(1<<20)
    successes=0;bins=[];entries=[];counts=Counter()
    for h in ids:
        counts['charts_attempted']+=1
        try:
            first=json.loads(get('/api/charts/'+h))
            if 'leaderboard' not in first:raise ValueError('missing leaderboard')
            chart=first['chart'];data=[first]
            n=first['total_pages']
            for page in set([max(1,(n+1)//2),max(n,1)])-{1}:
                data.append(json.loads(get(f'/api/charts/{h}?page={page}')))
            sampled=0;accepted=0;mat=np.zeros((BUCKETS,3),dtype='int64')
            for page in data:
                has=[r for r in page['leaderboard'] if r['has_ghost'] and not r['is_cheated']]
                # At most 3 replay attempts per page, spread across the page.
                for k in np.unique(np.linspace(0,len(has)-1,min(3,len(has))).round().astype(int)):
                    r=has[k];blob=get(f'/ghosts/{h}/{int(r["player_id"])}');sampled+=1
                    try:judges,empty=decode(blob)
                    except ValueError as exc:
                        parts=blob.strip().rstrip(b',').split(b',')
                        suffix=parts[-1].strip() if parts else b''
                        counts['undecodable']+=1
                        counts['decoder_reason_'+str(exc)[:42]]+=1
                        counts['form_fields_'+str(min(9,len(parts)))+'_trailing_comma_'+str(blob.strip().endswith(b','))+'_endZ_'+str(suffix.endswith(b'Z'))+'_narrow_alphabet_'+str(bool(re.fullmatch(rb'[A-Za-z0-9@]+',suffix)))]+=1
                        continue
                    arr=np.frombuffer(judges,dtype='u1');o=np.bincount(arr,minlength=6)
                    if len(arr)!=r['combo_max'] or array_counts(o,empty)!=[r[g] for g in ('pgreat','great','good','bad','poor')]:
                        counts['discordant']+=1;continue
                    accepted+=1
                    for b,s in enumerate(np.array_split(arr,BUCKETS)):mat[b]+=(len(s),np.count_nonzero(s<=2),np.count_nonzero(s==3))
            if accepted>=3:
                for b,s in enumerate(mat):bins.append([h,b,accepted,*s.tolist()])
            entries.append([h,chart.get('play_count'),chart.get('clear_count'),chart.get('play_people'),chart.get('clear_people'),sampled,accepted]);successes+=1
        except urllib.error.HTTPError as e:
            counts['http_'+str(e.code)]+=1
            if e.code in (401,403,429):break
        except Exception as e:
            counts[type(e).__name__]+=1
            if not successes and counts['charts_attempted']>=2:break
    for name,head,values in [('public_api_pairs.csv',['md5','plays','clears','people','ever_cleared','replays_sampled','exact_pb_matches'],entries),('public_api_bins.csv',['md5','order_bin','verified','notes','bad_or_miss','good'],bins)]:
        with (out/name).open('w') as f:
            w=csv.writer(f);w.writerow(head);w.writerows(values)
    return {'charts_available':successes,**counts}

def array_counts(o,empty):
    return [int(o[5]),int(o[4]),int(o[3]),int(o[2]),int(o[1]+empty)]

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['xml','web']);ap.add_argument('arg');ap.add_argument('catalog');ap.add_argument('out',type=Path);a=ap.parse_args()
    result=xml_archive(Path(a.arg),sorted({l.split('\t')[0] for l in Path(a.catalog).read_text().splitlines()}),a.out) if a.mode=='xml' else public_web(Path(a.arg).read_text().splitlines(),a.out)
    (a.out/(a.mode+'_coverage.json')).write_text(json.dumps(result,indent=2));print(result)
