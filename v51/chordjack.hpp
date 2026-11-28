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
template<class Frames> ChordLoad chordLoad(const Frames& frames) {
    if(frames.empty())return {};
    std::vector<v47::PressureRow> bins(size_t(frames.back().t/v47::motorStep)+1);
    std::array<Stroke,8> chords{};int used=0;
    Stroke lastKey{-10.,0};int active=0;
    for(const auto& f:frames) {
        const unsigned mask=unsigned(f.keys)&127u;
        if(!mask)continue;
        Stroke current{f.t,mask};
        if(motorPop(mask)>=2) {
            double weight=0.;
            // Read the chord line through single-key decorations and fixed
            // doubles. Limit skipped distinct chords to prevent incidental
            // matches between unrelated shapes far apart in a dense stream.
            for(int j=used-1;j>=0 && j>=used-3;--j) {
                const auto& middle=chords[j];
                if(current.t-middle.t>.40)break;
                for(int k=j-1;k>=0 && k>=j-3;--k) {
                    if(middle.t-chords[k].t>.40)break;
                    const double skipped=double(used-1-j+j-1-k);
                    weight=std::max(weight,grip(chords[k],middle,current)/(1.+.55*skipped));
                }
            }
            if(used && motorPop(lastKey.keys)==1 && lastKey.t>chords[used-1].t)
                weight=std::max(weight,grip(chords[used-1],lastKey,current));
            if(weight>0.){bins[size_t(f.t/v47::motorStep)][0]+=weight; ++active;}
            if(used==int(chords.size())) {
                std::move(chords.begin()+1,chords.end(),chords.begin());--used;
            }
            chords[used++]=current;
        }
        lastKey=current;
    }
    const auto summary=v47::summarizeMotor(bins,0);
    return {summary[0],summary[1],summary[2],summary[4],double(active)};
}
}
