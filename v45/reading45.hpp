#pragma once
#include "v37_measure.hpp"

namespace chart_radar::v45 {
struct Reading {
    double equivalentSeconds=0.,peak=0.,peakTime=0.,sustained=0.,upper=0.,mean=0.,exposure=0.;
    double dose() const { return (.35*peak+.4*upper+.25*sustained)*(-std::expm1(-equivalentSeconds/8.)); }
};
inline Reading measureReading(const DecodedChart& chart,const std::vector<v37::Frame>& frames) {
    Reading result;
    if(frames.empty() || chart.changes.empty())return result;
    const int length=int(std::floor(frames.back().t))+1;
    struct Segment { double time,position,speed; };
    std::vector<Segment> motion{{0.,0.,1.}};
    double speed=1.;
    const auto add=[&](double at,double next){
        const auto last=motion.back();at=std::max(last.time,at);
        if(at==last.time)motion.back().speed=next;
        else motion.push_back({at,last.position+(at-last.time)*last.speed,next});
    };
    for(const auto& c:chart.changes){
        if(c.stop>0.){add(c.time-c.stop,0.);add(c.time,speed);}
        else {speed*=c.ratio*(c.reversal?-1.:1.);add(c.time,speed);}
    }
    const auto position=[&](double t){
        const auto it=std::upper_bound(motion.begin(),motion.end(),t,[](double at,const Segment& item){return at<item.time;});
        const auto& v=it==motion.begin()?motion.front():*(it-1);
        return v.position+(t-v.time)*v.speed;
    };
    // Effective screen travel includes frozen intervals. This also handles BPM/STOP
    // encodings that simulate ordinary scroll with thousands of alternating commands.
    const double width=.32;
    std::vector<double> current,prior,normal;current.reserve(frames.size());
    for(const auto& frame:frames) {
        const double t=chart.notes.front().start+frame.t;
        const double middle=position(t);
        current.push_back((middle-position(t-width))/width);
        prior.push_back((position(t-width)-position(t-2.*width))/width);
        if(std::abs(current.back())>1.e-8)normal.push_back(std::abs(current.back()));
    }
    if(normal.empty())return result;
    auto median=normal.begin()+normal.size()/2;
    std::nth_element(normal.begin(),median,normal.end());const double base=*median;
    const auto contrast=[&](double a,double b){
        const double m=std::max(std::abs(a),std::abs(b));
        if(m<1.e-8*base)return 0.;
        const double distance=std::min(1.,std::abs(a-b)/m);
        return std::max(0.,(distance-.04)/.96);
    };
    std::vector<double> bins(length); double total=0.;
    for(size_t i=0;i<frames.size();++i) {
        const auto& f=frames[i];
        const double deviation=contrast(current[i],base);
        const double change=contrast(current[i],prior[i]);
        const double read=deviation+(1.-deviation)*change;
        const double hits=v37::pop(f.keys)+int(f.scratch);
        bins[std::clamp(int(f.t),0,length-1)]+=hits*read;total+=hits;
    }
    std::vector<double> prefix(length+1);
    std::partial_sum(bins.begin(),bins.end(),prefix.begin()+1);
    result.mean=prefix.back()/length;result.exposure=prefix.back()/std::max(1.,total);
    const int shortWidth=std::min(length,2),longWidth=std::min(length,8);
    std::vector<double> windows;
    for(int t=0;t+shortWidth<=length;++t) {
        const double load=(prefix[t+shortWidth]-prefix[t])/shortWidth;windows.push_back(load);
        if(load>result.peak){result.peak=load;result.peakTime=t;}
    }
    for(int t=0;t+longWidth<=length;++t)result.sustained=std::max(result.sustained,(prefix[t+longWidth]-prefix[t])/longWidth);
    const auto count=(windows.size()+9)/10;
    std::nth_element(windows.begin(),windows.end()-count,windows.end());
    result.upper=std::accumulate(windows.end()-count,windows.end(),0.)/count;
    if(result.peak>0.) result.equivalentSeconds=prefix.back()/result.peak;
    return result;
}
}
