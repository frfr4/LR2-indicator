#include "catalog.hpp"
#include <iostream>
#include <iomanip>
using namespace chart_radar;
static v44::Sections synthetic(std::vector<unsigned> masks,std::vector<double> times,int rows=360,int gauge=450,bool scroll=false) {
    DecodedChart chart{{},{},double(gauge),bms::Layout(7),2};RadarTempo tm;
    tm.tempos={{0,150}};tm.beatTempos={{0,150}};tm.mainVotes[150]=rows;
    double t=0.;
    for(int i=0;i<rows;++i) {
        unsigned m=masks[size_t(i)%masks.size()];
        for(int k=0;k<8;++k)if(m&(1u<<k))chart.notes.push_back({t,t,k,t*2.5});
        t+=times[size_t(i)%times.size()];
    }
    if(scroll){chart.changes={{t*.2,.25,0},{t*.55,4,0}};}
    return v44::measure(chart,tm);
}
int main(int argc,char**argv) {
    const std::vector<double> gap{.075};
    const auto jack=synthetic({1},gap),chord=synthetic({3},gap),notes=synthetic({1,4,16,2,32,8,64},gap),
        moving=synthetic({3,5,9,17},gap),scratch=synthetic({128},gap),del=synthetic({1,2,4,8,16,32,64},{.038,.044,.09}),
        warp=synthetic({1,4,16,2,32,8,64},gap,360,450,true),regular=synthetic({1,4,16,2,32,8,64},gap,360,66),
        longRun=synthetic({1,4,16,2,32,8,64},gap,2400);
    const auto jc=v44::scores(jack),cc=v44::scores(chord),nc=v44::scores(notes);
    for(auto m:{notes,jack,chord,moving,scratch,del,warp,longRun}) {
       for(auto a:detailOrder)std::cout<<v44::scores(m)[a]<<" ";std::cout<<"\n";
    }
    if(jc[Jack]<=nc[Jack] || cc[chart_radar::Chord]<=jc[chart_radar::Chord] || jc[Tech]!=0 || cc[Tech]!=0)return 2;
    if(moving.dose[Density]!=chord.dose[Density]||moving.dose[Tech]<=chord.dose[Tech])return 3;
    if(scratch.dose[Scratch]<=0 || scratch.dose[Density]>0 || del.dose[Stair]<=notes.dose[Stair])return 4;
    if(warp.dose[Soflan]<=0||longRun.dose[Stamina]<=notes.dose[Stamina])return 5;
    if(regular.dose!=notes.dose || (!regular.gaugeFlags) || warp.dose[Density]!=notes.dose[Density])return 6;
    for(int i=0;i<Count;++i){auto m=notes;m.dose[i]+=1000.;auto v=v44::scores(m);auto s=v44::scores(notes);
      for(int j=0;j<Count;++j)if(i!=j && v[j]!=s[j])return 7;
      if(v[i]<s[i]||v44::compound(v)<v44::compound(s))return 8;
    }
    if(argc==1)return 0;
    if(argc!=4)return 9;
    const std::filesystem::path assets=argv[1],samples=argv[2],cache=argv[3];std::filesystem::create_directories(cache);
    ChartCatalog catalog((assets/"charts-v26.tsv").string(),(cache/"pack.db").string());
    const std::string absent(32,'a');
    ChartCatalog direct((cache/"none").string(),(cache/"local.db").string());
    int checked=0;
    for(auto& f:std::filesystem::directory_iterator(samples)){
      const auto id=f.path().stem().string();auto expected=catalog.find(id);
      auto fromChart=direct.resolve(id,f.path().string(),7,true,true);auto info=catalog.selectionStats(id,7);
      if(!expected||!fromChart||!info||!catalog.poorExtra(id,7))return 10;
      for(int i=0;i<Count;++i)if(std::abs((*expected)[i]-(*fromChart)[i])>.021){std::cerr<<id<<" "<<i<<" "<<(*expected)[i]<<" "<<(*fromChart)[i]<<"\n";return 11;}
      if(catalog.gaugeFlags(id,7)!=direct.gaugeFlags(id,7))return 12;
      ++checked;
    }
    ChartCatalog reopened((cache/"none").string(),(cache/"local.db").string());
    if(checked<5||!reopened.gaugeFlags("90709c02ee7092b30907df62ed3bed40",7))return 13;
    std::cout<<checked<<" known / uncatalogued Windows paths and all eight independent axes verified\n";
}
