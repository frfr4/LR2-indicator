#pragma once
#include "v37_measure.hpp"
namespace chart_radar::v46 {
constexpr size_t fields=16;
using Local=std::array<double,fields>;
using LocalAxes=std::array<Local,Count>;
// For each pattern and second, count native demand and the keys and shapes
// encountered while it is active. Zero pattern demand contributes nothing.
inline LocalAxes passages(const std::vector<Scores>& events,const std::vector<double>& scroll,
                          const std::vector<v37::Frame>& frames) {
    LocalAxes result{};if(events.empty())return result;
    std::vector<double> hits(events.size()),grips(events.size()),motions(events.size());
    double last=-100.,lastGap=1.;unsigned previous=0,previous2=0;
    for(const auto& f:frames){
        size_t b=std::clamp(int(f.t),0,int(events.size()-1));
        int width=v37::pop(f.keys);
        hits[b]+=width+int(f.scratch);
        grips[b]+=std::max(width-1,0)+v37::pop(f.holds)*.25;
        if(width){
            double gap=f.t-last;
            double speed=std::clamp((.24-gap)/.18,0.,1.);
            double shift=v37::pop(f.keys^previous)/double(std::max(1,v37::pop(f.keys|previous)));
            double uneven=std::clamp(std::abs(gap-lastGap)/.08,0.,1.);
            motions[b]+=speed*(.25*width+shift*(.35+.35*uneven+.30*(f.keys!=previous2)));
            previous2=previous;previous=f.keys;last=f.t;lastGap=gap;
        }
    }
    for(int a=0;a<Count;++a){
        std::array<std::vector<double>,4> sums;
        for(auto& v:sums)v.assign(events.size()+1,0.);
        for(size_t b=0;b<events.size();++b){
            double load=a==Soflan?(scroll.empty()?0.:scroll[b]):events[b][a];
            double active=-std::expm1(-load);
            sums[0][b+1]=sums[0][b]+load;
            sums[1][b+1]=sums[1][b]+active*hits[b];
            sums[2][b+1]=sums[2][b]+active*grips[b];
            sums[3][b+1]=sums[3][b]+active*motions[b];
        }
        size_t n=events.size();
        auto& out=result[a];
        for(int j=0;j<3;++j){
            for(int k=0;k<2;++k){
                size_t width=std::min(n,size_t(k?16:3));
                for(size_t b=0;b+width<=n;++b)
                    out[2*j+k]=std::max(out[2*j+k],(sums[j][b+width]-sums[j][b])/width);
            }
        }
        out[6]=sums[0].back();out[7]=sums[1].back();
        for(int j=0;j<4;++j){
            out[8+j]=sums[j].back()/n;
            size_t width=std::min(n,size_t(32));
            for(size_t b=0;b+width<=n;++b)
                out[12+j]=std::max(out[12+j],(sums[j][b+width]-sums[j][b])/width);
        }
    }
    return result;
}
}
