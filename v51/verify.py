"""Check the shipped table against reported patterns and the Walkure peak bands."""
import csv
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def rows(path):
    return {r[0]:r[1:] for r in csv.reader(path.read_text(encoding='utf-8').splitlines(),delimiter='\t')}

def verify():
    stored=rows(ROOT/'charts-v51.tsv')
    previous=rows(ROOT.parent/'v50/charts-v50.tsv')
    assert set(previous)<=set(stored)
    for k,old in previous.items():
        assert all(float(stored[k][i])==float(old[i]) for i in (1,2,5,6,7,8,9,10,11)),k
    scores={k:tuple(float(v) for v in row[:8]) for k,row in stored.items()}
    cases=rows(ROOT/'screens.tsv')
    for k in cases:
        vals=scores[k]
        assert vals[4]==max(vals) and vals[3]>0.,k
    assert len(cases)==8
    st=rows(ROOT/'st12.tsv')
    assert len(st)==21 and st.keys()<=scores.keys()
    print('Stella st12 CHORD > 1000',sum(scores[k][4]>1000 for k in st),'/',len(st))
    with (ROOT.parent/'v50/peak-reference.tsv').open(encoding='utf-8') as src:
        anchors=list(csv.DictReader(src,delimiter='\t'))
    for band,a,b,n in [(0,100.,200.,49),(1,700.,800.,99)]:
        peaks=[max(scores[r['md5']]) for r in anchors if int(r['band'])==band]
        assert len(peaks)==n and all(a<=peak<=b for peak in peaks),(band,min(peaks),max(peaks))
        print('Walkure range',a,b,len(peaks),min(peaks),max(peaks))
if __name__=='__main__':verify()
