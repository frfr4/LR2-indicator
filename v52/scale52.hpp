#pragma once
#include "weights52.hpp"
#include "presentation.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace chart_radar::v52 {
using Inputs=std::vector<double>;
inline Inputs physicalInputs(const v44::Sections& m,const Scores& physical,const Scores& raw) {
    Inputs x;
    x.reserve(248);
    const auto append=[&](double v){x.push_back(std::copysign(std::log1p(std::abs(v)),v));};
    for(const auto& group:{physical,raw})for(auto a:detailOrder)append(group[a]);
    for(double v:{m.pattern.distributed,m.pattern.repeated,m.pattern.coordinated,
                  m.duration,m.heads,m.avgDensity,m.endDensity,m.afterDensity})append(v);
    for(const auto& group:{m.dose,m.peak,m.sustained})for(auto a:detailOrder)append(group[a]);
    for(double v:m.pressure)append(v);
    for(auto a:detailOrder)for(double v:m.human[a])append(v);
    return x;
}

// Shared smooth basis functions are fitted across chart families. A song never selects a coefficient.
inline Inputs evaluate(const Inputs& x,const fitted::Model& model) {
    Inputs z(x.size()),b;
    b.reserve(1+3*x.size()+3*model.centers);
    b.push_back(1.);
    for(size_t i=0;i<x.size();++i) {
        z[i]=std::clamp((x[i]-model.mean[i])/model.deviation[i],-6.,6.);
        b.push_back(z[i]);
    }
    for(double d:z)b.push_back(.6*std::max(0.,d-.4));
    for(double d:z)b.push_back(.6*std::max(0.,-d-.4));
    Inputs distances(model.centers,0.);
    for(size_t j=0;j<model.centers;++j) {
        const auto* center=model.prototypes+j*x.size();
        for(size_t i=0;i<x.size();++i){const double d=z[i]-center[i];distances[j]+=d*d;}
        distances[j]/=double(x.size());
    }
    for(double width:{.35,1.2,3.})
        for(double d:distances)b.push_back(5.*std::exp(-width*d));
    Inputs result(model.outputs,0.);
    for(size_t j=0;j<model.outputs;++j) {
        const auto* weights=model.weights+j*b.size();
        for(size_t i=0;i<b.size();++i)result[j]+=weights[i]*b[i];
    }
    return result;
}
inline double smooth(double x) {
    x=std::clamp(x,0.,1.);
    return x*x*(3.-2.*x);
}
inline double physicalLoad(const v44::Sections& m,const Scores& physical,const Scores& raw) {
    auto r=raw;
    r[Density]=m.pattern.distributed;
    r[Jack]=std::max(r[Jack],m.pattern.repeated);
    r[Chord]=std::max(r[Chord],m.pattern.coordinated);
    return std::sqrt(*std::max_element(r.begin(),r.end()) * *std::max_element(physical.begin(),physical.end()));
}
inline Inputs gaugeInputs(const v44::Sections& m) {
    Inputs g;
    const auto add=[&](double v){g.push_back(std::copysign(std::log1p(std::abs(v)),v));};
    for(double v:{m.total,m.normalTotal,m.poor,double(m.judgeRank)})add(v);
    for(double v:m.gaugePath)add(v);
    return g;
}
inline double softBounds(double v,double lo,double hi) {
    constexpr double width=8.;
    if(v<lo+width)return lo+width*width/(width+lo+width-v);
    if(v>hi-width)return hi-width*width/(width+v-hi+width);
    return v;
}
inline Inputs compactInputs(const Inputs& x,const Inputs& gauge,double skill) {
    Inputs summary={skill,std::max(0.,skill-4.),std::max(0.,skill-10.),std::max(0.,skill-16.)};
    for(size_t i:{0,3,4,5,16,17,18,19,20,21,22,23,52,90,130,135,61,66,70})summary.push_back(x[i]);
    for(size_t i:{4,5,8,9,12,13,14,20,23,24,25})summary.push_back(gauge[i]);
    return summary;
}
inline double hardFromInputs(const Inputs& x,const Inputs& gauge,double duration,double heads,double easy,double hard) {
    const double supported=smooth((duration-20.)/32.)*smooth((heads-100.)/180.);
    if(supported<=0.)return hard;
    const double skill=5.*evaluate(x,fitted::auxiliary)[0];
    auto compact=compactInputs(x,gauge,skill);
    compact.push_back(easy);
    compact.push_back(hard);
    const double correction=.5*evaluate(compact,fitted::hardResidual)[0];
    const double proposed=std::round(100.*(hard+supported*std::clamp(correction,-2.,2.)))/100.;
    return easy>=0.?std::max(easy,proposed):proposed;
}
inline double peakFromInputs(Inputs x,const Inputs& gauge,double load,double duration,double heads) {
    if(load<=0.)return 0.;
    const double skill=5.*evaluate(x,fitted::auxiliary)[0];
    const auto summary=compactInputs(x,gauge,skill);
    x.insert(x.end(),{skill,std::max(0.,skill-5.),std::max(0.,skill-12.),std::max(0.,skill-17.)});
    x.insert(x.end(),gauge.begin(),gauge.end());
    const auto value=evaluate(x,fitted::peak);
    double peak=500.+100.*(.65*value[0]+.35*evaluate(summary,fitted::compact)[0]);
    constexpr size_t last=std::size(fitted::correction)-1;
    const double location=std::clamp((peak-75.)/10.,0.,double(last));
    const auto left=size_t(location),right=std::min(last,left+1);
    peak+=fitted::correction[left]+(location-left)*(fitted::correction[right]-fitted::correction[left]);
    const auto& cut=fitted::cuts;
    const double low=smooth((value[1]-cut[0]+1.8)/1.8)*smooth((626.-load)/65.);
    const double high=smooth((value[2]-cut[1]+1.8)/1.8)*smooth((load-535.)/70.)*smooth(cut[2]-value[3]+1.);
    const double lowScale=softBounds(peak,101.,199.);
    const double highScale=softBounds(peak,701.,799.);
    peak+=low*(lowScale-peak)+high*(highScale-peak);
    const double supported=smooth((duration-20.)/32.)*smooth((heads-100.)/180.);
    const double shortScale=.78*load*(.48+.52*smooth(duration/22.));
    peak=supported*peak+(1.-supported)*shortScale;
    return std::clamp(peak,std::max(0.,load-600.),2.2*load);
}
inline Scores project(const Scores& measured,double peak) {
    const double strongest=*std::max_element(measured.begin(),measured.end());
    Scores result{};
    if(strongest<=0. || peak<=0.)return result;
    for(size_t i=0;i<result.size();++i)
        result[i]=std::round(100.*peak*std::pow(measured[i]/strongest,1.25))/100.;
    return result;
}
}
