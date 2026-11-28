#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace chart_radar::v52 {
// Half-second bins retain both short runs and the sustained cost of reusing fingers.
// Aggregate the two hands symmetrically. Split the centre key between them.
using Pressure = std::array<double,8>;
constexpr size_t spectraSize=3*8*5;
using Spectra=std::array<double,spectraSize>;
template<class Frames> Spectra pressure(const Frames& frames) {
    Spectra out{};
    if(frames.empty())return out;
    const double origin=frames.front().t;
    const size_t length=size_t(std::max(0.,frames.back().t-origin)*2.)+1;
    std::vector<Pressure> bins(length);
    std::array<double,7> last{};last.fill(-1.e6);
    unsigned previous=0;double prevTime=-1.e6;
    for(const auto& frame:frames) {
        const unsigned mask=frame.keys&127u;if(!mask)continue;
        auto& b=bins[std::min(length-1,size_t(std::max(0.,frame.t-origin)*2.))];
        double left=0.,right=0.,strain=0.,tight=0.,within=0.;
        for(int k=0;k<7;++k)if(mask&(1u<<k)) {
            const double gap=std::max(.02,frame.t-last[k]);
            const double speed=std::min(16.,1./gap);
            strain+=std::min(4.,std::pow(speed/4.,1.35));
            tight+=std::max(0.,speed-4.);
            if(k<=3)left+=(k==3?.5:1.);
            if(k>=3)right+=(k==3?.5:1.);
            last[k]=frame.t;
        }
        const double keys=left+right;
        within=std::max(0.,left-1.)+std::max(0.,right-1.);
        b[0]+=keys;b[1]+=std::max(left,right);b[2]+=strain;b[3]+=tight;
        b[4]+=keys*std::max(0.,keys-1.);
        b[5]+=within;
        if(frame.t-prevTime<.30) {
            b[6]+=v47::motorPop(mask&previous)*std::min(4.,.25/std::max(.025,frame.t-prevTime));
            b[7]+=v47::motorPop(mask^previous)*std::min(4.,.20/std::max(.025,frame.t-prevTime));
        }
        previous=mask;prevTime=frame.t;
    }
    size_t col=0;
    for(int width:{2,8,24}) {
        Pressure sum{};std::array<std::vector<double>,8> values;
        const size_t used=std::min(length,size_t(width));
        for(size_t i=0;i<length;++i) {
            for(size_t j=0;j<sum.size();++j) {
                sum[j]+=bins[i][j];
                if(i>=used)sum[j]-=bins[i-used][j];
                if(i+1>=used)values[j].push_back(std::max(0.,sum[j])*2./used);
            }
        }
        for(auto& v:values) {
            std::sort(v.begin(),v.end());
            for(double p:{.5,.8,.93,.98,1.}) {
                const double x=p*(v.size()-1);
                const auto a=size_t(x),b=std::min(a+1,v.size()-1);
                out[col++]=v[a]+(x-a)*(v[b]-v[a]);
            }
        }
    }
    return out;
}
}
