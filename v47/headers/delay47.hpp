#pragma once
#include "mechanics47.hpp"

namespace chart_radar::v47 {
// Separately timed fingers in a chord or burst. A uniform, moderately fast
// stream has no within-group compression. Very tight rolls can still qualify.
template<class Frame>
inline std::array<double,10> staggerActions(const std::vector<Frame>& frames) {
    if(frames.empty())return {};
    struct Hit {double t;unsigned keys;};
    std::vector<Hit> hits;hits.reserve(frames.size());
    for(const auto& f:frames)if(f.keys)hits.push_back({f.t,f.keys});
    std::vector<PressureRow> bins(size_t(frames.back().t/motorStep)+1);
    for(size_t i=1;i<hits.size();++i){
        double dt=hits[i].t-hits[i-1].t;
        if(dt<=0. || dt>=.085 || hits[i].keys==hits[i-1].keys)continue;
        // Typical local pulse on both sides, excluding the gap under test.
        std::array<double,16> around{};int n=0;
        size_t left=i>8?i-8:1,right=std::min(i+9,hits.size());
        for(size_t j=left;j<right;++j)if(j!=i){
            double gap=hits[j].t-hits[j-1].t;
            if(gap>0.)around[n++]=std::min(.35,gap);
        }
        double typical=dt;
        if(n){const int q=(n-1)*3/4;std::nth_element(around.begin(),around.begin()+q,around.begin()+n);typical=around[q];}
        const double before=i>1?hits[i-1].t-hits[i-2].t:dt;
        const double after=i+1<hits.size()?hits[i+1].t-hits[i].t:dt;
        const double compression=ramp((typical/std::max(.009,dt)-1.22)/1.30);
        const double boundary=ramp((std::min(.28,std::max(before,after))/std::max(.009,dt)-1.38)/1.55);
        const double tight=urgency(dt,.050,.026);
        const double relative=std::max(compression,.65*boundary)*urgency(dt,.085,.043);
        const unsigned both=hits[i].keys&hits[i-1].keys,either=hits[i].keys|hits[i-1].keys;
        const double separate=1.-double(motorPop(both))/motorPop(either);
        const double speed=.050/std::max(.016,dt);
        const double demand=std::max(tight,relative)*speed*(.55+.45*separate);
        bins[std::min(bins.size()-1,size_t(hits[i].t/motorStep))][MDelay]+=demand;
    }
    return summarizeMotor(bins,MDelay);
}
}
