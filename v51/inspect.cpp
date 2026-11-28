#include "model44.hpp"
#include "presentation.hpp"
#include "chordjack.hpp"
#include <fstream>
#include <iomanip>
using namespace chart_radar;
int main(int argc,char** argv) {
    if(argc!=3)return 1;
    const std::filesystem::path out=argv[2];
    std::ofstream ratings(out/"ratings.tsv"), ratios(out/"features.tsv");
    ratings<<std::fixed<<std::setprecision(2);ratios<<std::setprecision(12);
    for(const auto& entry:std::filesystem::directory_iterator(argv[1])) {
        if(entry.path().extension()!=".bms")continue;
        const auto id=entry.path().stem().string();
        RadarTempo tm;auto chart=decodeChart(entry.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tm);
        auto measured=v44::measure(chart,tm);
        const auto scores=v44::scores(measured);
        ratings<<id;for(auto a:detailOrder)ratings<<'\t'<<scores[a];ratings<<'\n';
        double main=0.;auto frames=v37::timeline(chart,tm,main);
        const auto physical=v47::physicalAxes(measured.human,measured,measured.scratch,measured.stagger);
        const auto raw=v47::patternAxes(measured,physical);const auto v=v51::chordLoad(frames);
        std::array<int,8> widths{};for(auto& f:frames)++widths[v47::motorPop(f.keys&127)];
        ratios<<id;for(auto a:detailOrder)ratios<<'\t'<<raw[a];
        ratios<<'\t'<<*std::max_element(physical.begin(),physical.end());
        for(double x:{v.burst,v.repeated,v.sustained,v.active,v.transitions})ratios<<'\t'<<x;
        for(int n:widths)ratios<<'\t'<<n;
        const auto lamps=v44::chartLamps(measured,chart.judgeRank);
        auto traits=assessPassages(chart.notes,7,chart.total).traits;
        traits.endSpike|=measured.gaugePath[gauge47::EndingSpike]!=0.;
        ratios<<'\t'<<int(traits.endSpike)<<'\t'<<traits.recoveryShortfall<<'\t'<<extraPoorCents(gaugeNoteCount(chart),int(chart.total))<<'\t'<<lamps.hard<<'\n';
    }
}
