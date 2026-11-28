#include "model44.hpp"
#include "presentation.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
using namespace chart_radar;
int main(int argc,char**argv) try {
    if(argc<3)return 1;
    std::ofstream output(argv[1]);output<<std::fixed<<std::setprecision(2);
    for(int j=2;j<argc;++j) {
        std::ifstream input(argv[j]);if(!input)throw std::runtime_error("missing feature file");
        std::string line;
        while(std::getline(input,line)) {
            std::istringstream row(line);std::string id;row>>id;
            std::array<double,297> f{};
            for(double& n:f)if(!(row>>n))throw std::runtime_error("missing chart observation "+id);
            Scores physical{},raw{},shape{};v44::Sections s{};
            size_t col=0;
            for(auto* a:{&physical,&raw,&shape})for(auto id:detailOrder)(*a)[id]=f[col++];
            s.pattern.distributed=f[24];s.pattern.repeated=f[25];s.pattern.coordinated=f[26];
            s.duration=f[29];s.heads=f[30];s.avgDensity=f[31];s.endDensity=f[32];s.afterDensity=f[33];s.total=f[34];s.normalTotal=f[35];s.poor=f[36];s.judgeRank=int(f[37]);
            col=38;
            for(auto* group:{&s.dose,&s.peak,&s.sustained})for(auto a:detailOrder)(*group)[a]=f[col++];
            col=65;
            for(auto& v:s.pressure)v=f[col++];
            for(auto a:detailOrder)for(auto& v:s.human[a])v=f[col++];
            for(auto& v:s.gaugePath)v=f[col++];
            for(auto& v:s.scratch)v=f[col++];
            const auto measured=v47::patternShape(s,physical,raw);
            if(shape!=measured)throw std::runtime_error("native shape mismatch "+id);
            const double load=v52::physicalLoad(s,physical,raw);
            const auto x=v52::physicalInputs(s,physical,raw),g=v52::gaugeInputs(s);
            const auto result=v52::published(s,measured,raw,x,g,load);
            output<<id;
            for(auto a:detailOrder)output<<'\t'<<result[a];
            for(size_t i=62;i<65;++i)output<<'\t'<<int(f[i]);
            const auto lamps=v52::extendedLamps(s,result,f[27],v52::hardFromInputs(x,g,s.duration,s.heads,f[27],f[28]));
            output<<'\t'<<lamps.hard<<'\t'<<((int(f[287])&1)?-1.:lamps.easy)<<'\n';
        }
    }
    return output.good()?0:2;
} catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 3;}
