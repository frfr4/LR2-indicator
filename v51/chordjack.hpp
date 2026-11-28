#pragma once
#include "mechanics47.hpp"
namespace chart_radar::v51 {
using v47::motorPop;
using v47::urgency;
struct Stroke {double t;unsigned keys;};
struct ChordLoad {double burst{},repeated{},sustained{},active{},transitions{};};
inline double speed(double gap) {
    return urgency(gap,.40,.17)*std::pow(.15/std::max(.055,gap),.85);
}
// Three connected attacks establish a grip change. A common finger may pass
// the repeated work to another finger on the next attack.
inline double grip(const Stroke& a,const Stroke& b,const Stroke& c) {
    const unsigned ab=a.keys&b.keys,bc=b.keys&c.keys;
    if(!ab||!bc||a.keys==b.keys||b.keys==c.keys)return 0.;
    const unsigned returns=a.keys&~b.keys&c.keys;
    if(!returns)return 0.;
    const int width=motorPop(c.keys),previous=motorPop(b.keys);
    if(width<2 || motorPop(a.keys)<2)return 0.;
    const double rate=std::min(speed(c.t-b.t),speed(b.t-a.t));
    const double paired=std::sqrt(double(motorPop(ab)*motorPop(bc)));
    // A two-key chord with only one recurring lane is less constraining than
    // a wider grip in which multiple fingers must release and strike together.
    const double span=std::sqrt((width-1.)*(.6+.4*previous));
    return rate*span*std::sqrt(double(motorPop(returns)))*std::sqrt(paired);
}
struct Contact {double pressure=0.;unsigned fingers=0;};
struct GripLine {
    std::array<Stroke,8> chords{};
    int used=0;
    Stroke lastKey{-10.,0};
    Contact strike(const Stroke& current) {
        Contact result;
        auto observe=[&](const Stroke& first,const Stroke& middle,double attenuation) {
            const double pressure=attenuation*grip(first,middle,current);
            const unsigned fingers=current.keys&(first.keys|middle.keys);
            if(pressure>result.pressure)result={pressure,fingers};
            else if(pressure>0. && pressure==result.pressure)result.fingers|=fingers;
        };
        if(motorPop(current.keys)>=2) {
            for(int j=used-1;j>=0 && j>=used-3;--j) {
                const auto& middle=chords[j];
                if(current.t-middle.t>.40)break;
                for(int k=j-1;k>=0 && k>=j-3;--k) {
                    if(middle.t-chords[k].t>.40)break;
                    const int skipped=used-k-2;
                    observe(chords[k],middle,1./(1.+.55*skipped));
                }
            }
            if(used && motorPop(lastKey.keys)==1 && lastKey.t>chords[used-1].t)
                observe(chords[used-1],lastKey,1.);
            if(used==int(chords.size())) {
                std::move(chords.begin()+1,chords.end(),chords.begin());--used;
            }
            chords[used++]=current;
        }
        lastKey=current;
        return result;
    }
};
inline double coordinatedScore(const std::array<double,10>& rates,double coverage) {
    const double load=.20*rates[0]+.43*rates[1]+.27*rates[2]+.10*rates[4];
    const double support=v47::ramp(coverage/.55);
    const double excess=std::max(0.,load-65.);
    // Beyond the ordinary Walkure calibration population, use a continuous
    // upper tail with bounded slope for exceptionally fast, wide repeated grips.
    return 140.*std::pow(load,.59)*(.55+.52*support)
        + .70*excess*excess/(1.+excess/75.)*(.25+.75*support);
}
template<class Frames> ChordLoad chordLoad(const Frames& frames) {
    if(frames.empty())return {};
    std::vector<v47::PressureRow> bins(size_t(frames.back().t/v47::motorStep)+1);
    GripLine line;int active=0;
    for(const auto& f:frames)if(f.keys) {
        const auto contact=line.strike({f.t,unsigned(f.keys)&127u});
        bins[size_t(f.t/v47::motorStep)][0]+=contact.pressure;
        if(contact.pressure>0.)++active;
    }
    const auto s=v47::summarizeMotor(bins,0);
    return {s[0],s[1],s[2],s[4],double(active)};
}
}
