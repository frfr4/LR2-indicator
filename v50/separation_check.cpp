#include "model44.hpp"
#include "presentation.hpp"
#include <iostream>
#include <iomanip>
#include <stdexcept>
using namespace chart_radar;
namespace {
using Masks=std::vector<unsigned>;
using Gaps=std::vector<double>;
Scores sample(const Masks& keys,const Gaps& gaps,int count,bool scroll=false) {
    DecodedChart chart{{},{},450.,bms::Layout(7),2};
    RadarTempo tempo;
    tempo.tempos={{0,150}};tempo.beatTempos={{0,150}};tempo.mainVotes[150]=count;
    double t=0.;
    for(int i=0;i<count;++i) {
        unsigned mask=keys[size_t(i)%keys.size()];
        for(int k=0;k<8;++k)if(mask&(1u<<k))chart.notes.push_back({t,t,k,t*2.5});
        t+=gaps[size_t(i)%gaps.size()];
    }
    if(scroll)chart.changes={{t*.23,.25,0},{t*.51,4.,0}};
    auto score=v44::scores(v44::measure(chart,tempo));
    for(double v:score)if(!std::isfinite(v)||v<0)throw std::runtime_error("invalid score");
    return score;
}
void check(bool valid,const char* message){if(!valid)throw std::runtime_error(message);}
void print(const char* name,const Scores& s) {
    std::cout<<name;for(auto a:detailOrder)std::cout<<'\t'<<std::fixed<<std::setprecision(2)<<s[a];
    std::cout<<'\n';
}
}
int main() try {
    const Masks stairs{1,2,4,8,16,32,64}, blocks{15}, switchGrip{7,11,13,14};
    auto steady=sample(stairs,{.080},350), delay=sample(stairs,{.024,.136},350);
    auto jack=sample({1},{.080},350), shortJack=sample({1,1,4,16,32,8,64},{.080},350);
    auto fixed=sample(blocks,{.1},240), changing=sample(switchGrip,{.1},240);
    auto platter=sample({128},{.08},350), scroll=sample(stairs,{.080},350,true);
    auto sparse=sample(stairs,{.080},18);
    for(const auto& n: {std::pair<const char*,Scores>{"stream",steady},{"delay",delay},{"jack",jack},{"shortJack",shortJack},{"fixed",fixed},{"changing",changing},{"platter",platter},{"scroll",scroll},{"short",sparse}})print(n.first,n.second);
    check(steady[Density]>0. && steady[Tech]==0. && steady[chart_radar::Chord]==0.,"ordinary stream");
    check(delay[Stair]>steady[Stair]+250. && delay[Stair]>delay[Density] && delay[Tech]==0.,"evenly repeated split timing");
    check(jack[Jack]>jack[Density]*2. && jack[Jack]>shortJack[Jack]*2. && shortJack[Jack]>steady[Jack],"same lane and run length");
    check(fixed[chart_radar::Chord]==0. && fixed[Jack]>0. && changing[chart_radar::Chord]>fixed[chart_radar::Chord]+50.,"confirmed changing grip");
    check(changing[Tech]==0. && sample({1,4,16,64,16,4},{.05,.125},210)[Tech]==0.,"repeating motifs");
    check(platter[Scratch]>0. && platter[Scratch]==*std::max_element(platter.begin(),platter.end()),"isolated platter");
    check(scroll[Soflan]>steady[Soflan] && steady[Soflan]==0.,"speed changes");
    check(steady[Stamina]>2.*sparse[Stamina],"sustained duration");
    // Same set of chord masks and gap multiset in both trials. Break the
    // repeated choreography only in the second, keeping row count and NPS.
    Masks motif={3,12,97,2,49,8,5,66}, unpredictable;
    Gaps beat={.06,.10,.15,.09,.06,.10,.15,.09}, shuffled;
    unsigned state=981041u;
    for(int i=0;i<35;++i) {
        Masks m=motif;Gaps g=beat;
        for(size_t k=m.size()-1;k>0;--k) {
            state=1664525u*state+1013904223u;std::swap(m[k],m[(state>>8)%(k+1)]);
            state=1664525u*state+1013904223u;std::swap(g[k],g[(state>>8)%(k+1)]);
        }
        unpredictable.insert(unpredictable.end(),m.begin(),m.end());shuffled.insert(shuffled.end(),g.begin(),g.end());
    }
    auto regular=sample(motif,beat,280),irregular=sample(unpredictable,shuffled,280);
    print("regular",regular);print("irregular",irregular);
    check(regular[Tech]==0. && irregular[Tech]>60.,"matched regular vs irregular coordination");
    for(unsigned& m:unpredictable){
        unsigned reversed=0;for(int k=0;k<7;++k)if((m>>k)&1u)reversed|=1u<<(6-k);m=reversed;
    }
    const auto mirror=sample(unpredictable,shuffled,280);
    for(auto a:{Density,Tech,Stair,Jack,chart_radar::Chord,Stamina})
        check(std::abs(mirror[a]-irregular[a])<=.01,"mirrored inputs");
    return 0;
} catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
