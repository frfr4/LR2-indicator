#include "clear_estimate.hpp"
#include "presentation.hpp"
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace chart_radar;
int main(int argc,char**argv) {
 if(argc!=4)return 2;
 std::ofstream ax(argv[2]),sel(argv[3]);ax<<std::fixed<<std::setprecision(2);sel<<std::fixed<<std::setprecision(8);
 std::vector<std::filesystem::path> paths;
 for(auto& e:std::filesystem::directory_iterator(argv[1]))paths.push_back(e.path());
 std::sort(paths.begin(),paths.end());
 for(const auto& p:paths){
    auto id=p.stem().string();RadarTempo timing;
    auto chart=decodeChart(p,7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&timing);
    const auto m=v44::measure(chart,timing);const auto v=v44::scores(m);
    const auto pr=v44::chartLamps(m,chart.judgeRank);const auto tr=assessPassages(chart.notes,7,chart.total).traits;
    v41::SelectionStats stats;v41::measure(chart,timing,stats);
    ax<<id;for(auto a:detailOrder)ax<<'\t'<<v[a];
    ax<<'\t'<<int(tr.endSpike)<<'\t'<<tr.recoveryShortfall<<'\t'<<extraPoorCents(int(m.heads),int(m.total))<<'\t'<<pr.hard<<'\n';
    sel<<id<<'\t'<<stats.average<<'\t'<<stats.maximum<<'\t'<<pr.easy<<'\t'<<pr.hard<<'\t'<<m.gaugeFlags<<'\n';
 }
 return (ax.good()&&sel.good())?0:3;
}
