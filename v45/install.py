"""Install SOF-LAN v45 on the pinned v44 runtime."""
from pathlib import Path
import shutil,sys
P=Path(__file__).resolve().parent
def change(p,old,new):
 s=p.read_text(encoding='utf-8-sig')
 if s.count(old)!=1:raise ValueError(f'Unexpected {p.name}: {old}')
 p.write_text(s.replace(old,new),encoding='utf-8')
def install(r):
 for n in ['reading45.hpp','scale45.hpp']:shutil.copyfile(P/n,r/n)
 sec=r/'sections.hpp';change(sec,'#include "gauge_reference.hpp"','#include "gauge_reference.hpp"\n#include "reading45.hpp"')
 change(sec,'struct Sections {','struct Sections {\n    v45::Reading scrollReading{};')
 change(sec,'const auto frames=v37::timeline(chart,timing,main);','const auto frames=v37::timeline(chart,timing,main);\n    out.scrollReading=v45::measureReading(chart,frames);')
 model=r/'model44.hpp';change(model,'#include "params.hpp"','#include "params.hpp"\n#include "scale45.hpp"')
 change(model,'    return result;', '    result[Soflan]=std::round(100.*v45::readingScale*x.scrollReading.dose())/100.;\n    return result;')
 cat=r/'catalog.hpp';s=cat.read_text()
 for old,new in [('charts-v44.tsv','charts-v45.tsv'),('selection-v44.tsv','selection-v45.tsv'),('radar_v44_chart','radar_v45_chart')]:
  assert old in s;s=s.replace(old,new)
 # An older non-7-key cache can still be read. 7-key data gets a fresh namespace.
 s=s.replace('        auto oldModes=query(ptr,','        auto priorModes=query(ptr,"SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=\'radar_v44_chart\'");\n        if(sqlite3_step(priorModes.get())==SQLITE_ROW)readCache(ptr,"SELECT * FROM radar_v44_chart WHERE mode<>7",entries);\n        auto oldModes=query(ptr,')
 cat.write_text(s)
 test=r/'tests/tech_check.cpp'
 change(test,'    if(argc==1)return 0;', '''    if(v44::scores(notes)[Soflan]!=0. || v44::scores(warp)[Soflan]<=0.)return 17;
    DecodedChart steady{{},{},450.,bms::Layout(7),2};RadarTempo tempo;
    tempo.tempos={{0.,150.}};tempo.mainVotes[150.]=200;
    for(int i=0;i<200;++i)steady.notes.push_back({1.+i*.08,1.+i*.08,i%7,0.});
    auto pulsed=steady;pulsed.changes.push_back({0.,2.,0.});
    for(int i=0;i<1100;++i)pulsed.changes.push_back({(i+1)*.016,1.,.008});
    if(v44::scores(v44::measure(pulsed,tempo))[Soflan]>1.)return 18;
    auto speeds=steady;speeds.changes={{4.,.25,0.},{8.,4.,0.}};auto extra=speeds;
    for(const auto& n:speeds.notes)if(n.start>11.)extra.notes.push_back({n.start,n.end,(n.lane+1)%7,0.});
    std::stable_sort(extra.notes.begin(),extra.notes.end(),[](const Note& a,const Note& b){return a.start<b.start;});
    auto plain=v44::scores(v44::measure(speeds,tempo)),dense=v44::scores(v44::measure(extra,tempo));
    if(plain[Soflan]<=0. || plain[Soflan]!=dense[Soflan] || dense[Density]<=plain[Density])return 19;
    if(argc==1)return 0;''')
if __name__=='__main__':install(Path(sys.argv[1])/'LR2/chart_radar')
