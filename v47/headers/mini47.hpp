#pragma once
#include "mechanics47.hpp"

namespace chart_radar::v47 {
struct MiniEvidence { int bouts=0; int transitions=0; };
template<class Frame>
inline std::array<double,10> miniJacks(const std::vector<Frame>& frames,MiniEvidence* evidence=nullptr) {
    MiniEvidence stats;
    if(frames.empty()){if(evidence)*evidence=stats;return {};}
    struct Hit {double t;unsigned keys;};
    std::vector<Hit> rows;
    std::array<std::vector<int>,7> lane;
    for(const auto& f:frames)if(f.keys){
        const int index=int(rows.size());
        rows.push_back({f.t,unsigned(f.keys)});
        for(int k=0;k<7;++k)if(f.keys&(1u<<k))lane[k].push_back(index);
    }
    std::vector<PressureRow> bins(size_t(frames.back().t/motorStep)+1);
    for(int k=0;k<7;++k){
        const auto& hits=lane[k];const unsigned key=1u<<k;
        unsigned nearby=0;
        for(int j=0;j<7;++j)if(std::abs(j-k)<=2 && j!=k)nearby|=1u<<j;
        for(size_t first=0;first<hits.size();){
            size_t end=first+1;
            while(end<hits.size()){
                const int gapRows=hits[end]-hits[end-1];
                const double gap=rows[hits[end]].t-rows[hits[end-1]].t;
                if(gap>.185 || gap<.018 || gapRows>3 || (gapRows==3&&gap>.135))break;
                ++end;
            }
            const int count=int(end-first);
            if(count>=2 && count<=4){
                const int lo=hits[first],hi=hits[end-1];
                // Read both the embedded repeat and its entry/exit. A short repeat
                // inside a constant single key or constant chord has no moving fingers.
                int before=lo,after=hi;
                if(before>0 && rows[lo].t-rows[lo-1].t<.16)--before;
                if(after+1<int(rows.size()) && rows[hi+1].t-rows[hi].t<.16)++after;
                double motion=0.,insideMotion=0.,otherHeads=0.;
                for(int i=before;i<=after;++i){
                    const unsigned companions=rows[i].keys&~key;
                    otherHeads+=motorPop(companions);
                    if(i==before)continue;
                    const unsigned changed=companions^(rows[i-1].keys&~key);
                    const double movement=motorPop(changed&nearby)+.48*motorPop(changed&~nearby);
                    motion+=movement;
                    if(i>lo&&i<=hi)insideMotion+=movement;
                }
                if(motion>0.){
                    unsigned always=rows[lo].keys&~key;
                    for(size_t j=first+1;j<end;++j)always&=rows[hits[j]].keys;
                    const double fixedCompanions=1./(1.+2.*motorPop(always));
                    const double changes=std::sqrt((.38*motion+.62*insideMotion)/std::max(1,after-before));
                    const double coactivity=1.+.25*otherHeads/(after-before+1);
                    ++stats.bouts;stats.transitions+=count-1;
                    for(size_t j=first+1;j<end;++j){
                        const int at=hits[j],prev=hits[j-1];
                        const double dt=rows[at].t-rows[prev].t;
                        const double speed=urgency(dt,.20,.10)*std::pow(.10/std::max(.026,dt),1.35);
                        const double intervening=1./(1.+.55*(at-prev-1));
                        const double repetitions=1.+.18*double(j-first-1);
                        const size_t b=std::min(bins.size()-1,size_t(rows[at].t/motorStep));
                        bins[b][MTech]+=speed*intervening*changes*coactivity*fixedCompanions*repetitions;
                    }
                }
            }
            first=end;
        }
    }
    if(evidence)*evidence=stats;
    return summarizeMotor(bins,MTech);
}
}
