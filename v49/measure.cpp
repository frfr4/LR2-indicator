#include "model44.hpp"
#include "presentation.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace chart_radar;
int main(int argc,char** argv) try {
    if(argc!=3)return 1;
    std::vector<std::filesystem::path> paths;
    for(const auto& file:std::filesystem::directory_iterator(argv[1]))
        if(file.path().extension()==".bms")paths.push_back(file.path());
    std::sort(paths.begin(),paths.end());
    std::ofstream out(argv[2]);out<<std::setprecision(16);
    for(const auto& path:paths){
        const auto id=path.stem().string();
        RadarTempo timing;
        auto decoded=decodeChart(path,7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&timing);
        auto section=v44::measure(decoded,timing);
        if(decoded.notes.empty())throw std::runtime_error("empty chart "+id);
        out<<id;
        for(const auto& features:{section.grips.jack,section.grips.chord})
            for(double x:features)out<<'\t'<<x;
        // Baseline columns are used to confirm the source and the other six axes.
        auto old=v44::scores(section);
        for(auto a:detailOrder)out<<'\t'<<old[a];
        out<<'\n';
    }
    std::cout<<paths.size()<<" charts decoded\n";
    return out.good()?0:2;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 3;}
