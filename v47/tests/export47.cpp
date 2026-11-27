#include "catalog.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace chart_radar;
// Re-decode every chart without using the packed radar, physical rating or clear catalog.
int main(int argc,char** argv) try {
    if(argc!=3)return 1;
    std::vector<std::filesystem::path> files;
    for(const auto& f:std::filesystem::directory_iterator(argv[1]))
        if(f.is_regular_file() && f.path().stem().string().size()==32)files.push_back(f.path());
    std::sort(files.begin(),files.end());
    std::ofstream out(argv[2]);
    out<<"md5\tNOTES\tDELAY\tSCRATCH\tSOF-LAN\tJACK\tTECH\tCHORD\tSTAMINA\tphysical\teasy\thard\tgauge_flags\tend_spike\trecovery_shortfall\thard_extra_poor\taverage\tmaximum\n";
    out<<std::setprecision(15);
    for(const auto& path:files){
        auto id=path.stem().string();
        RadarTempo tm;
        auto chart=decodeChart(path,7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tm);
        auto section=v44::measure(chart,tm);
        auto scores=v44::scores(section);
        auto stats=v41::summarize(chart,tm,&section);
        auto traits=assessPassages(chart.notes,7,chart.total).traits;
        traits.endSpike|=section.gaugePath[gauge47::EndingSpike]!=0.;
        out<<id;
        for(auto s:scores)out<<'\t'<<s;
        out<<'\t'<<v44::compound(scores)<<'\t'<<stats.easy.value_or(-1.)<<'\t'<<stats.hard.value_or(-1.)
           <<'\t'<<section.gaugeFlags<<'\t'<<int(traits.endSpike)<<'\t'<<traits.recoveryShortfall
           <<'\t'<<extraPoorCents(gaugeNoteCount(chart),static_cast<int>(chart.total))
           <<'\t'<<stats.average<<'\t'<<stats.maximum<<'\n';
    }
    return out.good()?0:2;
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 3;}
