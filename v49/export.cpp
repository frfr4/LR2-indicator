#include "model44.hpp"
#include "presentation.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace chart_radar;
int main(int argc,char** argv) try {
    if (argc!=3) return 1;
    std::vector<std::filesystem::path> files;
    for(const auto& entry:std::filesystem::directory_iterator(argv[1]))
        if(entry.is_regular_file() && entry.path().extension()==".bms")files.push_back(entry.path());
    std::sort(files.begin(),files.end());
    std::ofstream out(argv[2]);out<<std::fixed<<std::setprecision(2);
    for(const auto& path:files) {
        auto id=path.stem().string();
        if(id.size()!=32)throw std::runtime_error("invalid chart key");
        RadarTempo tm;
        auto chart=decodeChart(path,7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tm);
        if(chart.notes.empty())throw std::runtime_error("empty chart "+id);
        auto sections=v44::measure(chart,tm);
        auto axes=v44::scores(sections);
        const auto lamps=v44::chartLamps(sections,chart.judgeRank);
        auto traits=assessPassages(chart.notes,7,chart.total).traits;
        traits.endSpike|=sections.gaugePath[gauge47::EndingSpike]!=0.;
        out<<id;for(auto axis:detailOrder)out<<'\t'<<axes[axis];
        out<<'\t'<<int(traits.endSpike)<<'\t'<<traits.recoveryShortfall<<'\t'
           <<extraPoorCents(gaugeNoteCount(chart),int(chart.total))<<'\t'<<lamps.hard<<'\n';
    }
    return out.good()?0:2;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 3;}
