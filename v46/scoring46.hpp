#pragma once
#include "cal46.hpp"
namespace chart_radar::v46 {
inline double localEstimate(const std::array<double,37>& x,const Envelope& fit){
    double value=fit.coeff[0];
    for(int k=0;k<fit.size;++k){
        const double t=x[k]/fit.scale[k];
        value+=fit.coeff[1+k]*t+fit.coeff[1+fit.size+k]*std::max(0.,t-.65);
    }
    return std::max(0.,100.*value);
}
inline double visualEnergy(const ScrollContext& c){
    const double change=c[4]+c[5]+.50*c[3]+.12*c[6];
    const double decisions=c[8]+c[9]+.12*c[6];
    return std::sqrt(change*decisions);
}
// The summary combines the finished scores. It cannot feed back into any axis.
inline double compositeRaw(const Scores& scores){
    std::array<double,2*Count+1> raw{};
    std::copy(scores.begin(),scores.end(),raw.begin());
    auto ranked=scores;
    std::sort(ranked.rbegin(),ranked.rend());
    std::copy(ranked.begin(),ranked.end(),raw.begin()+Count);
    double cubes=0.;
    for(double score:scores)cubes+=score*score*score;
    raw.back()=std::cbrt(cubes);
    double total=0.;size_t feature=0;
    for(double onset:{0.,250.,500.,750.,1000.})
        for(double input:raw)total+=jointWeights[feature++]*std::max(0.,input-onset);
    return total;
}
inline double corrected(const v44::Sections& m,int a,double original){
    if(original<=0.)return 0.;
    std::array<double,37> x{};
    x[0]=a==Soflan?m.scrollReading.dose():m.dose[a];
    std::copy(m.local[a].begin(),m.local[a].end(),x.begin()+1);
    if(a==Density)for(int k:{3,4,5,6,8,10,11,12,14,15,16})x[k]=0.;
    x[7]=std::sqrt(x[7]);x[8]=std::sqrt(x[8]);
    if(a==Soflan)std::copy(m.scrollReading.context.begin(),m.scrollReading.context.end(),x.begin()+17);
    const double low=localEstimate(x,cautious[a]),middle=localEstimate(x,typical[a]);
    // Continue past the well-sampled range on the axis's own ruler.
    const double tail=.65*std::max(0.,original-tailStart[a]);
    if(a==Soflan){
        const double visual=visualScale*visualEnergy(m.scrollReading.context);
        const double additional=std::max(0.,std::min(middle,low+15.)-visual);
        return std::min(original,visual+.30*additional+tail);
    }
    const auto& rule=policy[a];
    const double intrinsic=original+std::min(rule[0]*original,rule[0]*300.);
    const double limit=std::min(middle,low+rule[1]+rule[2]*std::max(0.,middle-650.));
    const double adjusted=std::min(intrinsic,limit+tail);
    return a==Density?.75*original+.25*adjusted:adjusted;
}
}
