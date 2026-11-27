#pragma once
#include <array>
#include <vector>
#include <cmath>
namespace chart_radar::v46 {
using ScrollContext=std::array<double,20>;
inline ScrollContext scrollContext(const std::vector<double>& rate,const std::vector<double>& prior,
                                   const std::vector<v37::Frame>& frames,double base) {
    // Separate deep slower scroll, acceleration, direction reversal and transitions.
    // Only notes at affected instants enter these scores.
    const size_t n=size_t(frames.back().t)+1;
    std::vector<std::array<double,10>> bins(n);
    size_t trailing=0;double previousTime=-100.,lastGap=1.;unsigned previousMask=0;
    for(size_t i=0;i<frames.size();++i){
        const double x=rate[i]/base,y=prior[i]/base;
        const auto& f=frames[i];const double keys=v37::pop(f.keys)+int(f.scratch);
        const double slow=std::clamp((.96-std::abs(x))/.96,0.,1.);
        const double fast=std::clamp(1.-1.04/std::max(1.,std::abs(x)),0.,1.);
        const double boundary=std::clamp((std::abs(x-y)/std::max({.02,std::abs(x),std::abs(y)})-.04)/.96,0.,1.);
        auto& b=bins[std::min(size_t(f.t),n-1)];
        b[0]+=keys*slow*slow;b[1]+=keys*fast*fast;b[2]+=keys*(x<0.);
        b[3]+=keys*boundary*boundary;
        while(trailing+1<i && frames[trailing+1].t<f.t-1.)++trailing;
        const double recent=std::abs(x-y);
        const double persistence=std::exp(-8.*(recent+std::abs(x-rate[trailing]/base)));
        b[4]+=keys*slow*slow*persistence;
        b[5]+=keys*(fast*fast+(x<0.))*persistence;
        unsigned mask=f.keys|(f.scratch?128u:0u);
        double gap=f.t-previousTime;
        double tempo=std::clamp((.28-gap)/.20,0.,1.);
        double variation=v37::pop(mask^previousMask)/double(std::max(1,v37::pop(mask|previousMask)));
        double rhythm=std::clamp(std::abs(gap-lastGap)/.12,0.,1.);
        double read=std::max({slow,fast,boundary,x<0.?1.:0.});
        // A simultaneous grip is one visual row. Counting every finger as a
        // separate reading decision overstates repeated chords during tempo ramps.
        double row=read*(1.+.10*std::max(0.,keys-1.));
        b[6]+=row;
        b[7]+=row*tempo*(.20+.65*variation+.15*rhythm);
        double changedTiming=std::clamp((std::abs(gap-lastGap)/std::max({.02,gap,lastGap})-.12)/.65,0.,1.);
        b[8]+=row*tempo*variation*changedTiming;
        b[9]+=row*variation*std::clamp((.148-gap)/.085,0.,1.);
        previousTime=f.t;previousMask=mask;lastGap=gap;

    }
    ScrollContext result{};
    for(size_t j=0;j<10;++j){
        std::vector<double> sums(n+1);
        for(size_t i=0;i<n;++i)sums[i+1]=sums[i]+bins[i][j];
        auto w=std::min(n,size_t(4));
        for(size_t i=0;i+w<=n;++i)result[j]=std::max(result[j],(sums[i+w]-sums[i])/w);
        result[10+j]=std::sqrt(sums.back());
    }
    return result;
}
}
