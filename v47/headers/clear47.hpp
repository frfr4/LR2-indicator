#pragma once
#include "sections.hpp"
#include "clear47_params.hpp"
#include "clear47_domain.hpp"

namespace chart_radar::v47 {
inline double abilityStars(double ability) {
    const auto& ruler=clearParams::ruler;
    const auto end=std::end(ruler);
    const auto upper=std::clamp(std::upper_bound(std::begin(ruler),end,ability),
                                std::begin(ruler)+1,end-1);
    const auto lower=upper-1;
    return 1.+double(lower-std::begin(ruler))+(ability-*lower)/(*upper-*lower);
}

// Source features use chart information available before the first play.
// Keep the public scale, fitted coefficients and feature order together.
inline std::array<double,2> chartLamps47(const v44::Sections& section,int rank) {
    std::array<double,107> raw{};
    size_t pos=0;
    for(const auto* values:{&section.dose,&section.peak,&section.sustained})
        for(double value:*values)raw[pos++]=std::log1p(value);
    raw[pos++]=std::log1p(section.duration);
    raw[pos++]=std::log1p(section.heads);
    raw[pos++]=section.avgDensity;
    raw[pos++]=section.endDensity;
    raw[pos++]=section.afterDensity;
    raw[pos++]=std::log(std::max(.001,section.total/std::max(1.,section.normalTotal)));
    raw[pos++]=std::log(std::max(.001,section.poor/10.));
    raw[pos++]=rank;
    for(const auto& axis:section.human)
        for(int field:{0,2,3,6,8,9})raw[pos++]=std::log1p(axis[field]);
    for(int field=0;field<gauge47::GaugeFlags;++field){
        const double value=section.gaugePath[field];
        raw[pos++]=std::copysign(std::log1p(std::abs(value)),value);
    }
    for(double value:section.scratch)raw[pos++]=std::log1p(value);
    constexpr size_t features=107,centers=144;
    using Coordinates=std::array<double,features>;
    Coordinates normal{};
    for(size_t j=0;j<features;++j)normal[j]=std::clamp((raw[j]-clearParams::mean[j])/clearParams::deviation[j],-6.,6.);
    auto distances=[&](const Coordinates& values) {
        std::array<double,centers> d{};
        for(size_t i=0;i<centers;++i) {
            for(size_t j=0;j<features;++j){
                const double delta=values[j]-clearParams::center[i][j];
                d[i]+=delta*delta;
            }
            d[i]/=features;
        }
        return d;
    };
    const bool easyPossible=(section.gaugeFlags&8)==0;
    auto evaluate=[&](const Coordinates& values) {
        std::array<double,3*features+2*centers> basis{};
        for(size_t j=0;j<features;++j) {
            basis[j]=values[j];
            basis[features+j]=std::max(0.,values[j]-.6);
            basis[2*features+j]=std::max(0.,values[j]+.6);
        }
        const auto d=distances(values);
        for(size_t i=0;i<centers;++i) {
            basis[3*features+i]=std::exp(-.60*d[i]);
            basis[3*features+centers+i]=std::exp(-1.80*d[i]);
        }
        std::array<double,2> result{};
        for(size_t g=0;g<2;++g) {
            std::array<double,2> prediction{};
            for(size_t target=0;target<2;++target)
                prediction[target]=std::inner_product(basis.begin(),basis.end(),
                    clearParams::weight[g][target],clearParams::bias[g][target]);
            result[g]=.25*prediction[0]+.75*abilityStars(prediction[1]);
        }
        if(easyPossible)result[1]=std::max(result[0],result[1]);
        return result;
    };
    auto lamps=evaluate(normal);
    if(lamps[0]<clearDomain::minimum[0]||lamps[0]>clearDomain::maximum[0]||
       lamps[1]<clearDomain::minimum[1]||lamps[1]>clearDomain::maximum[1]) {
        // Repeat the prediction with diminishing marginal changes beyond
        // observed features and the observed neighbourhood of physical charts.
        Coordinates checked{};
        for(size_t j=0;j<features;++j) {
            const double value=normal[j],low=clearDomain::low[j],high=clearDomain::high[j];
            checked[j]=std::clamp(value,low,high)+.45*std::log1p(std::max(0.,value-high)/.45)
                -.45*std::log1p(std::max(0.,low-value)/.45);
        }
        const auto d=distances(checked);
        const size_t nearest=std::min_element(d.begin(),d.end())-d.begin();
        const double distance=std::sqrt(d[nearest]);
        const double excess=std::max(0.,distance-clearDomain::radius[nearest]);
        if(excess>0.) {
            const double ratio=(distance-excess+.18*std::log1p(excess/.18))/distance;
            for(size_t j=0;j<features;++j)
                checked[j]=clearParams::center[nearest][j]+(checked[j]-clearParams::center[nearest][j])*ratio;
        }
        const auto supported=evaluate(checked);
        for(size_t g=0;g<2;++g) {
            const double edge=std::clamp(lamps[g],clearDomain::minimum[g],clearDomain::maximum[g]);
            const double delta=lamps[g]-edge;
            if(delta==0.)continue;
            const double sign=delta>0.?1.:-1.,extent=std::abs(delta);
            const double trust=std::exp(-std::max(0.,sign*(lamps[g]-supported[g])));
            lamps[g]=edge+sign*(trust*extent+(1.-trust)*std::log1p(extent));
        }
    }
    if(easyPossible)lamps[1]=std::max(lamps[0],lamps[1]);
    for(double& value:lamps)value=std::round(100.*value)/100.;
    return lamps;
}
}
