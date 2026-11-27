#include "catalog.hpp"
#include <cstdio>
#include <fstream>
#include <iostream>
#include <sstream>

using namespace chart_radar;
namespace fs=std::filesystem;

static std::string shown(std::optional<double> number) {
    if(!number)return "-";
    char text[48];
    std::snprintf(text,sizeof(text),"%.2f",*number);
    return text;
}
int main(int argc,char** argv) {
    if(argc!=4)return 1;
    fs::path source=argv[1],fixture=argv[2],tmp=argv[3];
    fs::create_directories(tmp);
    const auto table=tmp/"clear-v42.tsv", db=tmp/"cache.sqlite";
    fs::copy_file(source,table,fs::copy_options::overwrite_existing);
    const std::string synthetic(32,'a'),unknown(32,'b');
    std::ofstream(table,std::ios::app)<<synthetic<<" -102 2099 . 2543\n";
    std::ifstream f(source);
    std::string line,h,re,ie,rh,ih;
    size_t count=0;
    // Preload the same legacy rows that v41 would read from a user's existing cache.
    {
        ChartCatalog build((tmp/"empty.tsv").string(),db.string());
        v41::SelectionStats sample{9.75,18.25,20.01,21.01};
        while(std::getline(f,line)) {
            std::istringstream row(line);
            if(!(row>>h>>re>>ie>>rh>>ih))return 2;
            build.saveStats(h,7,sample);
            auto out=build.selectionStats(h,7);
            if(!out || shown(out->easy)!=shown(std::stoi(re=="."?ie:re)/100.) ||
               shown(out->hard)!=shown(std::stoi(rh=="."?ih:rh)/100.) ||
               out->average!=sample.average || out->maximum!=sample.maximum)return 3;
            ++count;
        }
        if(!build.resolve(synthetic,fixture.string(),7,true,true))return 4;
        auto out=build.selectionStats(synthetic,7);
        if(!out || shown(out->easy)!="-1.02" || shown(out->hard)!="25.43")return 5;
        build.saveStats(synthetic,14,sample);build.saveStats(unknown,7,sample);
        for(auto record:{build.selectionStats(synthetic,14),build.selectionStats(unknown,7)})
            if(!record || record->easy!=sample.easy || record->hard!=sample.hard)return 6;
    }
    {
        ChartCatalog reload((tmp/"empty.tsv").string(),db.string());
        auto out=reload.selectionStats(synthetic,7);
        if(!out || shown(out->easy)!="-1.02" || shown(out->hard)!="25.43" || out->average<=0.)return 7;
    }
    std::cout<<count<<" display rows, mixed lookup and inference, fresh decode, legacy cache, reopened cache and mode isolation passed.\n";
    return count?0:8;
}
