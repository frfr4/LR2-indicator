#include "sections.hpp"
#include <iostream>
#include <iomanip>
using namespace chart_radar;
int main(int argc,char**argv){
 if(argc!=2)return 1;std::cout<<std::setprecision(15);
 for(const auto& f:std::filesystem::directory_iterator(argv[1])){
  auto id=f.path().stem().string();RadarTempo t;
  auto c=decodeChart(f.path(),7,unsigned(std::stoul(id.substr(0,8),nullptr,16)),&t);
  auto m=v44::measure(c,t);std::cout<<id;
  for(const auto& group:m.local)for(double value:group)std::cout<<'\t'<<value;
  for(double value:m.scrollReading.context)std::cout<<'\t'<<value;
  std::cout<<'\n';
 }
}
