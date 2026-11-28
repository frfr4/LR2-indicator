#include "model44.hpp"
#include <iostream>
#include <iomanip>
#include <stdexcept>
using namespace chart_radar;
namespace {
void check(bool ok,const char* what) { if(!ok) throw std::runtime_error(what); }
struct Frame { double t; unsigned keys; };
v49::GripFeatures measure(const std::vector<unsigned>& pattern,double gap){
    std::vector<Frame> frames;
    for (size_t i=0;i<pattern.size();++i) frames.push_back({i*gap,pattern[i]});
    return v49::measureGrips(frames);
}
Scores score(const std::vector<unsigned>& pattern,double gap){
    DecodedChart chart{{},{},450.,bms::Layout(7),2};
    RadarTempo tempo;tempo.tempos={{0,150}};tempo.beatTempos={{0,150}};tempo.mainVotes[150]=int(pattern.size());
    for(size_t i=0;i<pattern.size();++i){
        for(int k=0;k<7;++k)if(pattern[i]&(1u<<k))chart.notes.push_back({i*gap,i*gap,k,i*gap*2.5});
    }
    return v44::scores(v44::measure(chart,tempo));
}
}
int main() try {
    const std::array<std::vector<unsigned>,4> examples{{{7,11,13,14,7},{15,14,7,14,15},{11,15,13,15},{15,15,15,15}}};
    for(size_t i=0;i<examples.size();++i){
        double lastJack=-1.,lastChord=-1.;
        for(double dt:{.15,.10,.075}){
            auto s=score(examples[i],dt);
            std::cout<<i+1<<" "<<dt<<" "<<s[chart_radar::Chord]<<" "<<s[Jack]<<"\n";
            check(s[Jack]>lastJack,"faster repeated keys");
            check(i<3 ? s[chart_radar::Chord]>lastChord && s[chart_radar::Chord]>0. : s[chart_radar::Chord]==0., "only changing chords score");
            lastChord=s[chart_radar::Chord];lastJack=s[Jack];
        }
        const auto reference=measure(examples[i],.1);
        std::array<int,4> columns{0,2,4,6};
        do {
            std::vector<unsigned> sample;
            for(unsigned mask:examples[i]){
                unsigned remapped=0;
                for(int k=0;k<4;++k) if(mask&(1u<<k)) remapped|=1u<<columns[k];
                sample.push_back(remapped);
            }
            auto alt=measure(sample,.1);
            check(alt.jack==reference.jack && alt.chord==reference.chord,"lane permutation");
        }while(std::next_permutation(columns.begin(),columns.end()));
    }
    for(unsigned mask=1;mask<128;++mask){
        const auto g=measure({mask,mask,mask,mask},.1);
        check(g.jack[7]>0. && g.chord[7]==0.,"fixed grip");
    }
    check(measure({3,12,3,12},.1).chord[7]==0.,"disjoint grips");
    check(measure({3,7,15},.1).chord[7]==0.,"only widening");
    check(measure({15,15,7,7,15,15},.1).chord[7]>0.,"release and reentry");
    check(measure({15,7,15},1.).chord[7]==0.,"isolated releases");
    return 0;
} catch(const std::exception& e) { std::cerr<<e.what()<<"\n";return 1; }
