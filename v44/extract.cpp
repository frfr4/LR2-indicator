#include "sections.hpp"
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace chart_radar;
int main(int argc,char**argv){
 if(argc!=3)return 2;
 std::ofstream o(argv[2]);o<<std::setprecision(12);
 for(const auto& f:std::filesystem::directory_iterator(argv[1])){
   const auto id=f.path().stem().string();RadarTempo tm;
   try{
     const auto chart=decodeChart(f.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&tm);
     const auto m=v44::measure(chart,tm);o<<id;
     for(const auto& a:{m.dose,m.peak,m.peakTime,m.sustained})for(auto v:a)o<<'\t'<<v;
     for(double v:{m.duration,m.heads,m.total,m.normalTotal,m.poor,m.typicalPoor,m.lastChange,m.afterDensity,m.endDensity,m.avgDensity,double(m.gaugeFlags),double(chart.judgeRank)})o<<'\t'<<v;
     o<<'\n';
   }catch(const std::exception& e){std::cerr<<id<<" "<<e.what()<<"\n";return 3;}
 }
 return !o.good();
}
