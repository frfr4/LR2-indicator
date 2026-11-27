#include "catalog.hpp"
#include <iostream>
#include <stdexcept>
using namespace chart_radar;
namespace fs=std::filesystem;

// The packaged fixture directory contains only the two generated v47 tables.
// Official and empirical lamp precedence have separate cache/selection tests.
int main(int argc,char** argv) try {
    if(argc!=4)return 1;
    const fs::path assets=argv[1],charts=argv[2],tmp=argv[3];
    fs::create_directories(tmp);
    const auto dbPath=tmp/"catalog47.sqlite";
    if(fs::exists(dbPath))throw std::runtime_error("use a fresh check directory");
    ChartCatalog catalog((assets/"none").string());
    std::vector<std::string> ids;
    for(const auto& f:fs::directory_iterator(charts))
        if(f.is_regular_file()&&f.path().stem().string().size()==32)ids.push_back(f.path().stem().string());
    std::sort(ids.begin(),ids.end());
    size_t points=0,statsCount=0;
    auto compare=[&](ChartCatalog& local,const std::string& id){
        auto packed=catalog.find(id),raw=local.find(id);
        auto a=catalog.selectionStats(id,7),b=local.selectionStats(id,7);
        auto ap=catalog.traits(id,7),bp=local.traits(id,7);
        if(!packed || !raw || !a || !b || !ap || !bp || *packed!=*raw ||
           a->easy!=b->easy || a->hard!=b->hard || std::abs(a->average-b->average)>1.e-7 || std::abs(a->maximum-b->maximum)>1.e-7 ||
           catalog.hardEstimate(id)!=local.hardEstimate(id) || catalog.gaugeFlags(id,7)!=local.gaugeFlags(id,7) ||
           ap->endSpike!=bp->endSpike || ap->recoveryShortfall!=bp->recoveryShortfall ||
           catalog.poorExtra(id,7)!=local.poorExtra(id,7))throw std::runtime_error("chart/cache mismatch "+id);
        points+=8;++statsCount;
    };
    {
        ChartCatalog local((tmp/"none").string(),dbPath.string());
        for(const auto& id:ids){
            if(!local.resolve(id,(charts/(id+".bms")).string(),7,true,true))throw std::runtime_error("resolve failed "+id);
            compare(local,id);
        }
    }
    ChartCatalog reopened((tmp/"none").string(),dbPath.string());
    for(const auto& id:ids)compare(reopened,id);
    std::cout<<ids.size()<<" chart files, "<<points<<" radar cells, "<<statsCount<<" complete scalar/flag rows across live calculation and SQLite reopen.\n";
    return ids.size()==6226?0:2;
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 3;}
