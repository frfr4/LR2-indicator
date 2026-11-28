#include "model44.hpp"
#include "MinaCalc.h"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
using namespace chart_radar;
using Skills=std::array<double,8>;
Skills rate(const std::vector<Note>& notes,int first,int count,Calc& calc) {
    std::vector<NoteInfo> rows;
    double start=0.;
    for(const auto& n:notes) {
        if(n.lane<first||n.lane>=first+count) continue;
        if(rows.empty())start=n.start;
        const double elapsed=n.start-start+.5;
        if(elapsed>=(max_intervals-2)*.5 || elapsed<0 || !std::isfinite(elapsed))return {};
        const float t=float(elapsed);const unsigned bit=1u<<(n.lane-first);
        if(!rows.empty() && rows.back().rowTime==t)rows.back().notes|=bit;
        else rows.push_back({bit,t});
    }
    if(rows.size()<4)return {};
    calc.ssr=false;calc.keycount=count;const auto result=calc.CalcMain(rows,1.F,.93F);Skills output{};
    if(result.size()==output.size())for(size_t i=0;i<output.size();++i)
        output[i]=std::isfinite(result[i])?std::max(0.f,result[i]):0.;
    return output;
}
int main(int argc,char** argv) {
    if(argc!=3)return 1;
    auto seven=std::make_unique<Calc>(),four=std::make_unique<Calc>();
    std::ofstream out(argv[2]);out<<std::setprecision(12);
    for(const auto& f:std::filesystem::directory_iterator(argv[1])) {
        if(f.path().extension()!=".bms")continue;
        auto id=f.path().stem().string();RadarTempo tempo;
        const auto chart=decodeChart(f.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tempo);
        const auto all=rate(chart.notes,0,7,*seven),l=rate(chart.notes,0,4,*four),r=rate(chart.notes,3,4,*four);
        out<<id;for(auto d:all)out<<'\t'<<d;
        for(size_t i=0;i<8;++i)out<<'\t'<<std::max(l[i],r[i]);
        for(size_t i=0;i<8;++i)out<<'\t'<<std::min(l[i],r[i]);
        out<<'\n';
    }
    return out.good()?0:2;
}
