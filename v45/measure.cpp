#include "reading45.hpp"
#include <iostream>
#include <iomanip>
using namespace chart_radar;
int main(int argc,char** argv){
 if(argc!=2)return 2;
 std::cout<<"md5,dose,peak,time,sustained,upper,mean,exposure\n"<<std::setprecision(13);
 for(const auto& f:std::filesystem::directory_iterator(argv[1])){
  const auto id=f.path().stem().string();RadarTempo t;
  auto c=decodeChart(f.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&t);
  double main=0.;auto m=v45::measureReading(c,v37::timeline(c,t,main));
  std::cout<<id<<','<<m.dose()<<','<<m.peak<<','<<m.peakTime<<','<<m.sustained<<','<<m.upper<<','<<m.mean<<','<<m.exposure<<'\n';
 }
}
