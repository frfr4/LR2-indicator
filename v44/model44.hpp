#pragma once
#include "sections.hpp"
#include "params.hpp"
namespace chart_radar::v44 {
inline double scaled(double x,const parameters::Curve& c) {
    int i=1;
    while(i+1<c.n && x>c.x[i])++i;
    return std::max(0.,c.y[i-1]+(x-c.x[i-1])*(c.y[i]-c.y[i-1])/(c.x[i]-c.x[i-1]));
}
inline Scores scores(const Sections& x) {
    Scores result{};
    for(int i=0;i<Count;++i)result[i]=std::round(100.*scaled(x.dose[i],parameters::curves[i]))/100.;
    return result;
}
inline double compound(const Scores& scores) {
    double sum=0.;for(double x:scores)sum+=x*x*x;
    return scaled(std::cbrt(sum),parameters::curves[Count]);
}
using ModelInput=std::array<double,32>;
inline ModelInput input(const Sections& x,int rank) {
    ModelInput v{};int j=0;
    for(const auto* a:{&x.dose,&x.peak,&x.sustained})
        for(double f:*a)v[j++]=std::log1p(f);
    v[j++]=std::log1p(x.duration);v[j++]=std::log1p(x.heads);
    v[j++]=x.avgDensity;v[j++]=x.endDensity;v[j++]=x.afterDensity;
    v[j++]=std::log(std::max(.001,x.total/std::max(1.,x.normalTotal)));
    v[j++]=std::log(std::max(.001,x.poor/10.));v[j]=rank;
    return v;
}
template<size_t N>
inline double predict(const ModelInput& x,const int (&roots)[N],const parameters::Node* nodes,double bias) {
    double pred=bias;
    for(int root:roots) {
        int i=root;
        while(nodes[i].field>=0)i=x[nodes[i].field]<=nodes[i].value?nodes[i].left:nodes[i].right;
        pred+=nodes[i].value;
    }
    return std::round(pred*100.)/100.;
}
struct Lamps {double easy,hard;};
inline Lamps chartLamps(const Sections& m,int rank) {
    const auto x=input(m,rank);
    const double e=predict(x,parameters::easyRoots,parameters::easyNodes,parameters::easyBias);
    const double h=predict(x,parameters::hardRoots,parameters::hardNodes,parameters::hardBias);
    return {e,std::max(e,h)};
}
}
