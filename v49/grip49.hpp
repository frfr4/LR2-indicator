#pragma once
#include "mechanics47.hpp"

namespace chart_radar::v49 {
struct GripFeatures {
    std::array<double,10> jack{}, chord{};
};

// Measure repeated key activations and changing grips independently. The lamp
// predictor keeps its v47 input features and the player's stored lamp history.
template<class Frame>
GripFeatures measureGrips(const std::vector<Frame>& frames) {
    using namespace v47;
    if (frames.empty()) return {};
    std::vector<PressureRow> bins(static_cast<size_t>(frames.back().t/motorStep)+1);
    std::array<double,7> lastDown, lastOmission;
    lastDown.fill(-100.);
    lastOmission.fill(-100.);
    unsigned previous=0;
    double previousTime=-100., pendingTime=-100., pendingWeight=0.;
    size_t pendingBin=0;
    for (const auto& f : frames) {
        const unsigned mask=unsigned(f.keys)&127u;
        if (!mask) continue;
        const double t=f.t;
        const auto bin=static_cast<size_t>(t/motorStep);
        double squared=0.;
        for (int k=0;k<7;++k) {
            if (!(mask&(1u<<k))) continue;
            const double effort=repress(t-lastDown[k]);
            squared+=effort*effort;
            lastDown[k]=t;
        }
        bins[bin][MJack]+=std::sqrt(squared);

        const unsigned dropped=previous&~mask, added=mask&~previous;
        const int common=motorPop(previous&mask), changed=motorPop(added|dropped);
        const double rate=repress(t-previousTime);
        if (motorPop(mask)<2 || motorPop(previous)<2 || !common || rate==0.) {
            lastOmission.fill(-100.);
            pendingWeight=0.;
        } else if (changed) {
            const double weight=rate*std::sqrt(double(common*changed));
            bool reentry=false;
            for (int k=0;k<7;++k) {
                if ((added&(1u<<k)) && repress(t-lastOmission[k])>0.) reentry=true;
                if (dropped&(1u<<k)) lastOmission[k]=t;
            }
            if (dropped || reentry) {
                bins[bin][MChord]+=weight;
                if (dropped && pendingWeight>0. && repress(t-pendingTime)>0.)
                    bins[pendingBin][MChord]+=pendingWeight;
                pendingWeight=0.;
            } else {
                // A widening alone becomes chord evidence only with a nearby release.
                pendingTime=t;pendingBin=bin;pendingWeight=weight;
            }
        }
        previous=mask;
        previousTime=t;
    }
    return {summarizeMotor(bins,MJack),summarizeMotor(bins,MChord)};
}
}
