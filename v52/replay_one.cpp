#include "catalog.hpp"
#include "presentation.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace chart_radar;
struct Counts { int keys=0,all=0; };
Counts oneSecond(const DecodedChart& chart) {
    struct Head { double t; bool key; };
    std::vector<Head> heads;
    std::array<double,8> held;held.fill(-1.e20);
    for(const auto& n:chart.notes) if(n.lane>=0 && n.lane<8 && n.start>held[n.lane]){
        heads.push_back({n.start,n.lane<7});held[n.lane]=n.end;
    }
    Counts result;size_t left=0;int keys=0;
    for(size_t i=0;i<heads.size();++i){
        keys+=int(heads[i].key);
        while(heads[i].t-heads[left].t>=1.)keys-=int(heads[left++].key);
        result.keys=std::max(result.keys,keys);
        result.all=std::max(result.all,int(i-left+1));
    }
    return result;
}
int main(int argc,char** argv) try {
    if(argc<4)return 1;
    const std::string temp=argv[1];
    std::ofstream out(argv[2]);out<<std::fixed<<std::setprecision(2);
    for(int i=3;i<argc;++i){
        const std::filesystem::path chart=argv[i];const auto id=chart.stem().string();
        RadarTempo tempo;
        const auto decoded=decodeChart(chart,7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tempo);
        const auto actual=oneSecond(decoded);
        auto cold=ChartCatalog(temp+"/none",temp+"/local.db");
        const auto axes=cold.resolve(id,chart.string(),7,true,true);
        const auto stats=cold.selectionStats(id,7);
        if(!axes || !stats || !stats->hard)throw std::runtime_error("missing "+id);
        auto warm=ChartCatalog(temp+"/none",temp+"/local.db");
        const auto again=warm.selectionStats(id,7);
        if(warm.find(id,7)!=axes || !again || again->easy!=stats->easy || again->hard!=stats->hard)
            throw std::runtime_error("cache mismatch "+id);
        out<<id;
        for(auto a:detailOrder)out<<'\t'<<(*axes)[a];
        out<<'\t'<<stats->easy.value_or(-1.)<<'\t'<<*stats->hard<<'\t'<<stats->average<<'\t'<<stats->maximum
           <<'\t'<<actual.keys<<'\t'<<actual.all<<'\n';
    }
    return !out.good();
} catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 3;}
