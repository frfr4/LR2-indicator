from install_measure import P,repl,install_measure
from pathlib import Path
import shutil,sys
def score_install(r):
 for n in ['cal46.hpp','scoring46.hpp']:shutil.copyfile(P/n,r/n)
 f=r/'model44.hpp'
 repl(f,'#include "scale45.hpp"','#include "scale45.hpp"\n#include "scoring46.hpp"')
 repl(f,'    return result;', '    for(int a=0;a<Count;++a)result[a]=std::round(100.*v46::corrected(x,a,result[a]))/100.;\n    return result;')
 repl(f,'parameters::curves[Count]','v46::overallCurve')
 f=r/'catalog.hpp';s=f.read_text()
 for name in ['charts-v','selection-v','radar_v']:
  suffix='_chart' if name=='radar_v' else '.tsv'
  old=name+'45'+suffix;assert old in s;s=s.replace(old,name+'46'+suffix)
 anchor='        auto priorModes=query(ptr,'
 if s.count(anchor)!=1:raise ValueError('v45 cache fallback')
 s=s.replace(anchor,'        auto recentModes=query(ptr,"SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=\'radar_v45_chart\'");\n        if(sqlite3_step(recentModes.get())==SQLITE_ROW)readCache(ptr,"SELECT * FROM radar_v45_chart WHERE mode<>7",entries);\n'+anchor)
 f.write_text(s)
 f=r/'tests/tech_check.cpp'
 repl(f,'    if(argc==1)return 0;', '''    // Changing an unrelated feature vector must leave every other score fixed.
    for(int a=0;a<Count;++a){
        auto altered=moving;for(auto& value:altered.local[a])value+=300.;
        const auto before=v44::scores(moving),after=v44::scores(altered);
        for(int j=0;j<Count;++j)if(j!=a && after[j]!=before[j])return 20;
        if(after[a]<before[a])return 21;
    }
    if(v44::scores(moving)[Density]!=v44::scores(chord)[Density])return 25;
    auto onlyJack=v44::scores(jack),onlyChord=v44::scores(chord),onlyDeck=v44::scores(scratch);
    if(onlyJack[Jack]!=*std::max_element(onlyJack.begin(),onlyJack.end()))return 22;
    if(onlyChord[chart_radar::Chord]!=*std::max_element(onlyChord.begin(),onlyChord.end()))return 23;
    if(onlyDeck[Scratch]!=*std::max_element(onlyDeck.begin(),onlyDeck.end()) || onlyDeck[Scratch]<=0.)return 24;
    if(argc==1)return 0;''')
if __name__=='__main__':
 r=Path(sys.argv[1])/'LR2/chart_radar';install_measure(r);score_install(r)
