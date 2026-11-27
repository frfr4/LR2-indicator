#pragma once
#include "sections.hpp"
#include "mechanics47.hpp"
#include "scratch47.hpp"
#include "delay47.hpp"
#include "axis47_params.hpp"
#include "compound47.hpp"
#include "mini_floor.hpp"
#include "observation47_params.hpp"
#include "params.hpp"
#include "scale45.hpp"
#include "scoring46.hpp"

namespace chart_radar::v47 {

inline std::array<double,37> measuredAxis(int axis, const HumanFeatures& motor,
                                          const v44::Sections& sections,
                                          const Scratch47& scratch,const std::array<double,10>& stagger) {
    std::array<double,37> result{};
    std::copy(motor[axis].begin(), motor[axis].end(), result.begin());
    if (axis == Soflan) {
        result[10] = sections.scrollReading.dose();
    } else {
        result[10] = sections.dose[axis];
        result[11] = sections.peak[axis];
        result[12] = sections.sustained[axis];
    }
    constexpr int contextFields[] = {0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15};
    for (size_t i=0; i<std::size(contextFields); ++i) {
        int field=contextFields[i];
        // Density counts keyheads regardless of their fingering or scratching.
        if (axis != Density || field == 0 || field == 1 || field == 8 || field == 12)
            result[13+i]=sections.local[axis][field];
    }
    if (axis==Stair) {
        const double share=std::min(1.,stagger[4]/std::max(1.e-8,motor[axis][4]));
        for (size_t j=10;j<27;++j)result[j]*=share;
        std::copy(stagger.begin(),stagger.end(),result.begin());
    }
    result[27]=std::sqrt(result[0]*result[6]);
    result[28]=std::sqrt(result[2]*result[16]);
    result[29]=std::sqrt(result[10]*result[26]);
    result[30]=std::sqrt(result[6]*result[17]);
    if (axis==Soflan) {
        const auto& c=sections.scrollReading.context;
        const double movement=c[4]+c[5]+.50*c[3]+.12*c[6];
        const double decisions=c[8]+c[9]+.12*c[6];
        result[31]=std::sqrt(movement*decisions);
    }
    if (axis==Scratch) {
        std::copy(scratch.begin(),scratch.end(),result.begin()+32);
        result[35]=std::min(scratch[3],scratch[4]);
        result[36]=.5*(scratch[3]+scratch[4]);
    }
    return result;
}

inline double measuredContinuation(double load,double measuredMaximum) {
    if (load<=measuredMaximum)return load;
    const double width=std::max(1.e-8,.05*measuredMaximum);
    return measuredMaximum+width*std::log1p((load-measuredMaximum)/width);
}

inline Scores axisScores(const HumanFeatures& motor,const v44::Sections& sections,
                         const Scratch47& scratch,const std::array<double,10>& stagger) {
    Scores scores{};
    for (int a=0; a<Count; ++a) {
        auto v=measuredAxis(a,motor,sections,scratch,stagger);
        for(size_t j=0;j<v.size();++j)v[j]=measuredContinuation(v[j],observation::maximum[a][j]);
        double estimate=0., conservative=0., typical=0.;
        for (size_t j=0; j<v.size(); ++j) {
            if (v[j]<=0.)continue;
            const double x=std::log1p(v[j]/axisfit::scale[a][j]);
            double left=0.;
            for (size_t k=0; k<std::size(axisfit::knots[a][j]); ++k) {
                if (x<=left)break;
                const double knot=axisfit::knots[a][j][k];
                double amount=(x-left)/std::max(.16,knot-left);
                if (k+1<std::size(axisfit::knots[a][j]))amount=std::min(1.,amount);
                estimate+=axisfit::increments[a][j][k]*amount;
                conservative+=axisfit::guardLow[a][j][k]*amount;
                typical+=axisfit::guardMid[a][j][k]*amount;
                left=knot;
            }
        }
        const double support=conservative+axisfit::guard[0]+axisfit::guard[2]*std::max(0.,typical-axisfit::guard[1]);
        double axis=100.*std::max(0.,std::min(estimate,support));
        if (a==Scratch) {
            const double platter=measuredContinuation(v[34]+std::sqrt(v[32]*v[33]),observation::platterMaximum);
            // A few scratches during dense key runs do not require the same
            // turntable action as repeated strokes, releases and restarts.
            const double disk=std::sqrt(v[10]*(.75*v[12]+.25*v[1]))+.50*platter;
            axis=std::min(axis,std::sqrt(axis*axisfit::diskScale*disk));
            axis=std::max(axis,axisfit::platterScale*platter);
        }
        if (a==Tech)axis=std::max(axis,mixedRehitFloor(sections.mini));
        if (a==Soflan) {
            const double original=std::round(100.*v45::readingScale*sections.scrollReading.dose())/100.;
            axis=std::min(v46::corrected(sections,a,original),std::round(100.*v45::readingScale*v[10])/100.);
        }
        scores[a]=std::round(100.*axis)/100.;
    }
    return scores;
}

inline double physicalRating(const Scores& scores) {
    std::array<double,2*Count+1> x{};
    std::copy(scores.begin(),scores.end(),x.begin());
    auto ranked=scores;
    std::sort(ranked.rbegin(),ranked.rend());
    std::copy(ranked.begin(),ranked.end(),x.begin()+Count);
    double cubes=0.;
    for (double s:scores)cubes+=s*s*s;
    x.back()=std::cbrt(cubes);
    double fit=0.;size_t i=0;
    for (const double lower:{0.,250.,500.,750.,1000.})
        for (double s:x)fit+=axisfit::joint[i++]*std::max(0.,s-lower);
    return joint47::summary(x,fit);
}
}
