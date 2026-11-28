"""Audit exactly the installed eight-axis table. Reference labels are used only in this program."""
from pathlib import Path
import argparse,csv,math
from zipfile import ZipFile
from itertools import combinations
import statistics
ROOT=Path(__file__).resolve().parent
AX=('NOTES','TECH','DELAY','JACK','CHORD','STAMINA','SCRATCH','SOF-LAN')
CENTER=(150,150,235,270,300,355,375,390,415,450,485,515,545,570,585,615,645,655,665,680,690,750,750,750)
def rows(path):
    result={}
    for l in path.read_text(encoding='utf-8-sig').splitlines():
        k,*v=l.split('\t')
        if k in result:raise ValueError('duplicate '+k)
        result[k]=v
    return result
def oj(h):
    return 100*math.exp((h-3)/3) if h<3 else 100+50*(h-3) if h<=5 else 200+(h-5)*500/18 if h<=23 else 700+50*(h-23)
def expected(h):
    if 3<=h<=5:return 100+(h-3)*50
    if 5<h<=24:return 200+(h-5)*500/19
    if 24<h<=25:return 700+(h-24)*100
def inspect(args):
    src=ROOT.parent;data=rows(args.charts);clear=rows(args.clear);cases=rows(src/'v51/screens.tsv');st=rows(src/'v51/st12.tsv')
    scores={k:list(map(float,v[:8])) for k,v in data.items()}
    if any(len(row)!=12 or not all(math.isfinite(float(v)) for v in row) for row in data.values()):raise ValueError('invalid chart table')
    with ZipFile(args.archive) as z:
        ref={k:(int(s),int(o),float(h)) for k,s,o,h in (l.split() for l in z.read('tests/test-labels.tsv').decode().splitlines())}
    tests=list(csv.DictReader((ROOT/'validation.tsv').open(),delimiter='\t'))
    official={k for k,v in clear.items() if v[2]!='.'}
    assert {r['md5'] for r in tests}==official and len(ref)==1200 and len(official)==1236
    assert {k for k in data}>=set(rows(src/'v51/charts-v51.tsv'))
    assert len(cases)==8 and all(scores[k][4]==max(scores[k]) and scores[k][3]>0 for k in cases)
    assert len(st)==21 and sum(scores[k][4]>1000 for k in st)>=4
    groups=[f'★{i}' for i in range(1,25)]+[f'★★{i}' for i in range(7)]
    stats={};point={};ss=[]
    for r in tests:
        k=r['md5'];truth=int(clear[k][2])/100;raw=float(data[k][-1]);record=int(clear[k][3])/100;top=max(scores[k])
        assert abs(top-float(r['peak']))<=.025 and abs(raw-float(r['chart_hard']))<=.011
        assert abs(truth-float(r['hard']))<1e-8
        buckets=['전체']+(['미사용 곡군'] if r['group']=='held-out' else [])
        for pop in buckets:
            for mode,level in [('원본 채보 HARD',raw),('공식 Walkure HARD',truth),('기록 기반 예상 HARD',record)]:
                mid=expected(level)
                if mid is not None:
                    tally=point.setdefault((pop,mode),[0,0]);tally[0]+=abs(top-mid)<=50+1e-8;tally[1]+=1
        if k in ref:
            s,o,h=ref[k];assert h==truth
            for i,mid,radius in ([(s-1,CENTER[s-1],50)] if s else [])+([(24+o,oj(h),25 if h>25 else 50)] if o>=0 else []):
                for pop in buckets:
                    for mode,level in [('원본 채보 HARD',raw),('기록 기반 예상 HARD',record)]:
                        s1=abs(round(100*level)-round(100*truth))<=(50 if truth>25 else 100)
                        s2=abs(top-mid)<=radius+1e-8
                        tally=stats.setdefault((pop,mode,i),[0,0,0,0])
                        for j,n in enumerate((1,s1,s2,s1 and s2)):tally[j]+=n
        ss.append([k,r['group'],r['star'],r['oj'],truth,raw,record,*scores[k],AX[scores[k].index(top)],top])
    for a,b,l,h,n in [(3,5,100,200,49),(24,25,700,800,99)]:
        peaks=[r[-1] for r in ss if a<=r[4]<=b]
        assert len(peaks)==n and all(l<=v<=h for v in peaks),(len(peaks),min(peaks),max(peaks))
    if args.out:
        args.out.mkdir(exist_ok=True,parents=True)
        def save(name,heads,rs):
            with (args.out/name).open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f);w.writerow(heads);w.writerows(rs)
        save('charts.csv',['MD5','학습 구분','발광','Overjoy','공식 HARD','원본 채보 예상 HARD','기록 기반 예상 HARD',*AX,'최고축','최고점'],ss)
        save('grades.csv',['표본','예상 경로','등급','목표(%)','등록 건수','HARD 적중','최고점 적중','동시 적중','동시 적중률(%)'],
             ([pop,m,groups[i],90 if i<24 else 85,*v,round(100*v[3]/v[0],2)] for (pop,m,i),v in sorted(stats.items())))
        save('direct.csv',['표본','기대점에 사용한 HARD','±50점 안의 차분','HARD 3–25 차분','일치율(%)'],
             ([pop,m,*v,round(100*v[0]/v[1],2)] for (pop,m),v in sorted(point.items())))
    success=True
    for pop in ('전체','미사용 곡군'):
        for mode in ('원본 채보 HARD','기록 기반 예상 HARD'):
            for first,last,threshold in [(0,24,.9),(24,31,.85)]:
                ns=[stats[(pop,mode,i)] for i in range(first,last) if (pop,mode,i) in stats]
                passed=sum(n[3]>=threshold*n[0] for n in ns)
                if pop=='전체' and mode=='원본 채보 HARD':success &= passed==last-first
                print(pop,mode,groups[first],groups[last-1],sum(r[3] for r in ns),'/',sum(r[0] for r in ns),'등급',passed,'/',len(ns))
    print('곡별 기대점',point)
    return success
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--charts',type=Path,default=ROOT/'charts-v52.tsv');p.add_argument('--clear',type=Path,default=ROOT.parent/'v43/clear-v43.tsv');p.add_argument('--archive',type=Path,default=ROOT.parent/'RadarV40.zip');p.add_argument('--out',type=Path);p.add_argument('--qualify',action='store_true')
    a=p.parse_args();ok=inspect(a);raise SystemExit(int(a.qualify and not ok))
