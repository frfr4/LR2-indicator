"""Build the native grip scale from hashed BMS measurements and previous score quantiles."""
import math
import sys
from pathlib import Path
from statistics import quantiles

def burden(features):
    return .25*features[0]+.45*features[1]+.30*features[2]

def percentile(values, fraction):
    ordered=sorted(values)
    index=(len(ordered)-1)*fraction
    lo=int(index)
    return ordered[lo]+(ordered[min(lo+1,len(ordered)-1)]-ordered[lo])*(index-lo)

def scale(rows, start, score):
    observed=[(burden(f[start:start+10]),f[score]) for f in rows]
    positive=[(x,y) for x,y in observed if x>0]
    xx,yy=zip(*positive)
    return [(0.,0.)]+[(percentile(xx,q),percentile(yy,q)) for q in (.15,.35,.55,.75,.90,.97)]

def evaluate(points, load):
    for (x1,y1),(x2,y2) in zip(points,points[1:]):
        if load<=x2:
            return y1+(y2-y1)*(load-x1)/(x2-x1)
    width=x2-x1
    return y2+(y2-y1)*math.log1p((load-x2)/width)

def read(path):
    return {p[0]:list(map(float,p[1:])) for l in Path(path).read_text().splitlines() if (p:=l.split())}
if __name__=='__main__':
    import zipfile
    from csv import DictReader
    features=read(sys.argv[1])
    exclusions={r['Song MD5 hash'] for r in DictReader(open(sys.argv[2],encoding='utf-8-sig')) if r['Song difficulty']=='★★8'}
    regular=[r for k,r in features.items() if k not in exclusions]
    scales=[scale(regular,0,23),scale(regular,10,24)]
    target=Path(sys.argv[4])
    head=['#pragma once','#include "grip49.hpp"','namespace chart_radar::v49 {','struct Knot { double load, score; };']
    for name,knots in zip(('jackScale','chordScale'),scales):
        assert all(x2>x and y2>y for (x,y),(x2,y2) in zip(knots,knots[1:]))
        head.append('inline constexpr Knot '+name+'[] = {'+', '.join('{%.15g, %.15g}'%p for p in knots)+'};')
    head.extend(['inline double gripScore(const std::array<double,10>& features, const Knot (&scale)[7]) {',
        '    const double load=.25*features[0]+.45*features[1]+.30*features[2];',
        '    for (size_t i=1;i<std::size(scale);++i) {',
        '        const auto &a=scale[i-1], &b=scale[i];',
        '        if (load<=b.load) return a.score+(b.score-a.score)*(load-a.load)/(b.load-a.load);',
        '    }','    const auto &a=scale[5], &b=scale[6];',
        '    return b.score+(b.score-a.score)*std::log1p((load-b.load)/(b.load-a.load));','}','}'])
    (target/'grip_scale49.hpp').write_text('\n'.join(head)+'\n')
    with zipfile.ZipFile(sys.argv[3]) as z:
        p=next(n for n in z.namelist() if n.endswith('/charts-v47.tsv'))
        catalog={c[0]:c for line in z.read(p).decode().splitlines() if (c:=line.split())}
    mismatch=[]
    for k,f in features.items():
        c=catalog[k]
        # Use the measured other six to avoid borrowing axes from a differently decoded chart.
        if any(abs(f[20+i]-float(c[i+1]))>.021 for i in range(8)):
            mismatch.append(k)
            continue
        for i,offset,sc in [(4,0,scales[0]),(5,10,scales[1])]:
            c[i]=f'{evaluate(sc,burden(f[offset:offset+10])):.2f}'
    (target/'charts-v49.tsv').write_text(''.join('\t'.join(catalog[k])+'\n' for k in sorted(features) if k not in mismatch))
    print(len(regular),'calibration files,',len(features)-len(mismatch),'verified baseline matches,',len(mismatch),'decode mismatches')
