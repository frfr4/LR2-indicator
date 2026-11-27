#pragma once
#include "mechanics47.hpp"
#include <stdexcept>

namespace chart_radar::v47 {
using Scratch47 = std::array<double,5>;
// A long scratch has a timed end, while an ordinary scratch has a single head.
// The end is a motor transition, not a new scored head or assumed direction change.
struct ScratchEvidence {
    int heads=0,holds=0,shortHolds=0,quickResumes=0,keysUnderHold=0;
    double totalHold=0.,minHold=0.,minResume=0.;
    std::array<double,5> peakSec{};
};
inline constexpr std::array<const char*,5> scratchFields={
    "bss_release_3s","bss_resume_12s","scratch_irregular_3s","scratch_grip_left_3s","scratch_grip_right_3s"};
template<class NoteType,class Frame>
inline Scratch47 scratchActions(const std::vector<NoteType>& notes,const std::vector<Frame>& frames,
                                ScratchEvidence* evidence=nullptr) {
    Scratch47 values{};ScratchEvidence meta;meta.peakSec.fill(-1.);
    if(notes.empty()||frames.empty()){if(evidence)*evidence=meta;return values;}
    struct Stroke {double start,end;};
    std::vector<Stroke> deck;const double origin=notes.front().start;
    for(const auto& n:notes)if(n.lane==7 && (deck.empty()||n.start-origin>deck.back().end+1.e-8))
        deck.push_back({n.start-origin,std::max(n.end,n.start)-origin});
    if(deck.empty()){if(evidence)*evidence=meta;return values;}
    meta.heads=int(deck.size());
    const double span=std::max(frames.back().t,deck.back().end);
    if(!std::isfinite(span) || span<0. || span>86400.)throw std::invalid_argument("invalid platter duration");
    const size_t count=size_t(span/motorStep)+1;
    std::vector<std::array<double,5>> bins(count);
    auto bin=[&](double t){return std::min(count-1,size_t(std::max(0.,t)/motorStep));};
    auto from=[&](double t){return std::lower_bound(frames.begin(),frames.end(),t,[](const Frame& f,double v){return f.t<v;});};
    double precedingGap=10.;
    for(size_t i=0;i<deck.size();++i){
        const auto& s=deck[i];
        const double duration=s.end-s.start;
        const double prev=i?s.start-deck[i-1].end:10.;
        const double after=i+1<deck.size()?deck[i+1].start-s.end:10.;
        const double period=i?s.start-deck[i-1].start:10.;
        const bool hold=duration>1.e-7;
        const double in=urgency(prev,.38,.085),out=urgency(after,.38,.085);
        if(hold){
            ++meta.holds;meta.totalHold+=duration;
            if(duration<=.25)++meta.shortHolds;
            if(meta.minHold==0.||duration<meta.minHold)meta.minHold=duration;
            if(after<=.20)++meta.quickResumes;
            if(i+1<deck.size() && (!meta.minResume||after<meta.minResume))meta.minResume=after;
            // A close short hold requires a quick change of control state, especially
            // when entered from scratch repeats or followed by another scratch onset.
            const double shortness=urgency(duration,.47,.09);
            bins[bin(s.end)][0]+=.25+.70*shortness+.60*shortness*in+.90*shortness*out;
            bins[bin(s.end)][1]+=out*(.55+.75*shortness+.40*in);
        }
        if(i>=2){
            double irregular=ramp((std::abs(period-precedingGap)/std::max({.035,period,precedingGap})-.08)/.65);
            bins[bin(s.start)][2]+=irregular*urgency(std::max(period,precedingGap),.5,.15)*
                                    (.5+std::min(2.5,.14/std::max(.035,std::min(period,precedingGap))));
        }
        precedingGap=period;
        // Capture the available near-side fingers around the platter action.
        // During extended holds count wrist/keyboard concurrence over the actual interval.
        for(auto f=from(s.start-.12);f!=frames.end()&&f->t<=s.end+.12;++f){
            if(!f->keys && !f->holds)continue;
            bool heldTime=hold && f->t>=s.start && f->t<=s.end;
            if(heldTime)meta.keysUnderHold+=motorPop(f->keys);
            for(int side=0;side<2;++side){
                const unsigned local=side?112u:7u;
                const unsigned pressed=f->keys&local,held=f->holds&local;
                const bool atHead=std::abs(f->t-s.start)<1.e-6;
                const bool atRelease=hold && std::abs(f->t-s.end)<.001;
                const bool nearEdge=atHead||atRelease;
                // Do not count the same held key in every neighbouring frame.
                const double contact=motorPop(pressed)+(nearEdge?.45*motorPop(held&~pressed):0.);
                if(!contact)continue;
                const double distance=std::min(std::abs(f->t-s.start),std::abs(f->t-s.end));
                const double edge=urgency(distance,.12,.015);
                const double weight=heldTime?.35+.65*edge:edge*(atHead?1.:.32);
                bins[bin(std::max(0.,f->t))][3+side]+=contact*weight*(1.+.30*in+.25*out);
            }
        }
    }
    for(int k=0;k<5;++k){
        const size_t width=k==1?48:12;double sum=0.;
        for(size_t i=0;i<bins.size();++i){
            sum+=bins[i][k];if(i>=width)sum-=bins[i-width][k];
            const double pressure=sum/(motorStep*width);
            if(pressure>values[k]+1.e-12){
                values[k]=pressure;meta.peakSec[k]=(i+1>=width?i+1-width:0)*motorStep;
            }
        }
    }
    if(evidence)*evidence=meta;
    return values;
}
}
