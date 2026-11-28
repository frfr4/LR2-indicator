#include "model44.hpp"
#include "presentation.hpp"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
using namespace chart_radar;
int main(int argc,char** argv) try {
    if(argc!=3) return 1;
    std::ofstream out(argv[2]);out<<std::setprecision(14);
    for(const auto& file:std::filesystem::directory_iterator(argv[1])) {
        if(file.path().extension()!=".bms") continue;
        const auto id=file.path().stem().string();
        RadarTempo tempo;
        const auto chart=decodeChart(file.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tempo);
        if(chart.notes.empty()) throw std::runtime_error("empty chart "+id);
        const auto m=v44::measure(chart,tempo);
        const auto v=v47::physicalAxes(m.human,m,m.scratch,m.stagger);
        const auto raw=v47::patternAxes(m,v);
        const auto score=v44::scores(m);
        const auto lamp=v44::chartLamps(m,chart.judgeRank);
        out<<id;
        for(const auto& group:{v,raw,score})for(auto a:detailOrder)out<<'\t'<<group[a];
        for(double value:{m.pattern.distributed,m.pattern.repeated,m.pattern.coordinated,lamp.easy,lamp.hard,
                          m.duration,m.heads,m.avgDensity,m.endDensity,m.afterDensity,m.total,m.normalTotal,m.poor,double(chart.judgeRank)})out<<'\t'<<value;
        for(const auto& group:{m.dose,m.peak,m.sustained})for(auto a:detailOrder)out<<'\t'<<group[a];
        auto trait=assessPassages(chart.notes,7,chart.total).traits;
        out<<'\t'<<int(trait.endSpike||m.gaugePath[gauge47::EndingSpike]!=0.)<<'\t'<<trait.recoveryShortfall
           <<'\t'<<extraPoorCents(gaugeNoteCount(chart),int(chart.total))<<'\n';
    }
    return out.good()?0:2;
} catch(const std::exception& e) { std::cerr<<e.what()<<'\n';return 3; }
