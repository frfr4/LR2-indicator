#pragma once
#include "mechanics47.hpp"

namespace chart_radar::v50 {
using v47::motorPop;
using v47::ramp;
using v47::urgency;
struct Load { double notes{},delay{},tech{},jack{},chord{},stamina{}; };
struct Hit { double t,beat,gap; unsigned keys,holds; };

// Mark both repetitions, including the opening of a motif. Local lookahead is
// appropriate when rating a chart offline. Scratch-only rows never split a key motif.
inline std::vector<bool> repeatedMotifs(const std::vector<Hit>& hits) {
    const size_t n=hits.size();
    std::vector<int> ends(n+1);
    for(size_t period=1;period<=32 && 2*period<=n;++period) {
        size_t run=0;
        for(size_t i=period;i<=n;++i) {
            bool same=false;
            if(i<n) {
                const Hit &a=hits[i],&b=hits[i-period];
                const double tolerance=std::max(.003,.09*std::min(a.gap,b.gap));
                same=a.keys==b.keys && a.holds==b.holds &&
                     (i==period || std::abs(a.gap-b.gap)<=tolerance);
            }
            if(same) {++run;continue;}
            if(run>=std::max<size_t>(period,3)) {++ends[i-run-period];--ends[i];}
            run=0;
        }
    }
    int coverage=0;std::vector<bool> learned(n);
    for(size_t i=0;i<n;++i) {coverage+=ends[i];learned[i]=coverage>0;}
    return learned;
}

// Charge the return only after observing an omitted key. At least one anchor
// must have survived every intervening chord. A plain release, a fixed block
// jack, a widening grip, or two unrelated chord blocks cannot earn this charge.
struct Omissions {
    struct Key {double dropped=-100.; unsigned anchor=0; int age=0;};
    std::array<Key,7> keys{};
    double update(const Hit& f,unsigned previous) {
        const auto common=f.keys & previous;
        if(!common || motorPop(f.keys)<2 || motorPop(previous)<2 || f.gap>.245) {keys={};return 0.;}
        const unsigned added=f.keys & ~previous, dropped=previous & ~f.keys;
        const double continuity=double(motorPop(common))/std::max(motorPop(f.keys),motorPop(previous));
        double count=0.;
        for(int k=0;k<7;++k) {
            const unsigned bit=1u<<k;
            Key& key=keys[k];
            key.anchor &= common;
            if(key.anchor && (added&bit) && key.age<=4) {
                const double elapsed=f.t-key.dropped;
                const double stability=double(motorPop(key.anchor))/std::max(1,motorPop(f.keys)-1);
                count+=urgency(elapsed,.49,.10)*std::sqrt(stability)*continuity;
            }
            if((added&bit) || !key.anchor)key=Key{};
            if(dropped&bit)key={f.t,common,0};
            if(f.keys!=previous)++key.age;
        }
        return std::sqrt(count)*urgency(f.gap,.245,.075)*(.12/std::max(.036,f.gap));
    }
};

inline double splitEffort(const std::vector<Hit>& h,size_t i) {
    if(!i)return 0.;
    const auto& f=h[i];const unsigned fresh=f.keys&~h[i-1].keys;
    if(!fresh || f.gap>=.106)return 0.;
    std::array<double,12> gaps{};int count=0;
    for(size_t j=std::max<size_t>(1,i>6?i-6:1);j<std::min(h.size(),i+7);++j)
        if(j!=i && h[j].gap>0. && h[j].gap<.4)gaps[count++]=h[j].gap;
    double pulse=f.gap;
    if(count) {std::sort(gaps.begin(),gaps.begin()+count);pulse=gaps[(count-1)*3/4];}
    const double contrast=ramp((pulse/f.gap-1.24)/1.06);
    // Uniform ultrafast rolls still require separate finger timings at high BPM.
    const double fine=urgency(f.gap,.063,.037);
    const double subdivision=ramp((f.beat/f.gap-5.0)/3.)*urgency(f.gap,.088,.040);
    const double precision=std::max({fine,contrast*urgency(f.gap,.106,.045),subdivision});
    const double independent=double(motorPop(fresh))/motorPop(f.keys);
    return precision*(.065/std::max(.021,f.gap))*independent;
}

inline double technicalEffort(const std::vector<Hit>& h,size_t i,bool learned) {
    if(learned || i<2)return 0.;
    const auto &a=h[i-2],&b=h[i-1],&c=h[i];
    if(c.gap>.31 || b.gap>.31 || b.keys==c.keys)return 0.;
    const unsigned changed=b.keys^c.keys;
    const double rush=urgency(c.gap,.30,.09);
    const double rhythm=ramp((std::abs(std::log2(c.gap/b.gap))-.22)/1.3);
    const int w=motorPop(c.keys),w0=motorPop(b.keys);
    const double regroup=ramp((std::abs(w-w0)+.5*std::abs(w0-motorPop(a.keys)))/2.);
    // Evaluate both fixed splits of the centre key so a mirror has equal cost.
    double conflict=1.;
    for(unsigned left:{7u,15u}) {
        const unsigned right=127u^left;
        const bool leftMoves=(changed&left)!=0, rightMoves=(changed&right)!=0;
        const int anchor=motorPop(b.keys&c.keys);
        const bool movingWhileHeld=((c.holds&~c.keys&left) && (changed&left)) ||
                                   ((c.holds&~c.keys&right) && (changed&right));
        const double asymmetric=leftMoves&&rightMoves ?
            ramp((std::abs(motorPop(changed&left)-motorPop(changed&right))+.5*anchor)/3.) : 0.;
        conflict=std::min(conflict,std::max(asymmetric,movingWhileHeld?.9:0.));
    }
    const double irregular=std::max(rhythm*std::max(regroup,conflict),regroup*conflict);
    return rush*irregular;
}

inline double rehit(double dt) {
    return urgency(dt,.257,.13)*std::pow(.135/std::max(.034,dt),1.18);
}

template<class Frames> Load measure(const Frames& frames) {
    if(frames.empty())return {};
    std::vector<Hit> h;h.reserve(frames.size());
    for(const auto& f:frames)if(f.keys) {
        const double gap=h.empty()?1.:std::max(.001,f.t-h.back().t);
        h.push_back({f.t,f.beat,gap,unsigned(f.keys)&127u,unsigned(f.holds)&127u});
    }
    if(h.empty())return {};
    const auto learned=repeatedMotifs(h);
    std::vector<v47::PressureRow> bins(size_t(h.back().t/v47::motorStep)+1);
    struct AnchorTrack { Omissions omissions; unsigned previous=0; double time=-100.; };
    std::array<AnchorTrack,7> anchors{};
    std::array<double,7> last{},prior{};last.fill(-100.);prior.fill(-100.);
    for(size_t i=0;i<h.size();++i) {
        const auto& f=h[i];auto& bin=bins[size_t(f.t/v47::motorStep)];
        const unsigned prev=i?h[i-1].keys:0;
        const double split=splitEffort(h,i);
        double jackSquares=0.,freshNotes=0.;
        for(int k=0;k<7;++k)if(f.keys&(1u<<k)) {
            const double dt=f.t-last[k],old=last[k]-prior[k];
            const double pressure=rehit(dt);
            const double alignment=prior[k]<0.?0.:
                ramp(1.-std::abs(std::log2(std::max(.001,old)/dt))/.78);
            const bool adjacent=(prev&(1u<<k))!=0;
            const double chain=prior[k]<0.?0.:urgency(old,.27,.14)*alignment;
            const double isolated=adjacent?.45:.20;
            // Two strikes already count. Sustaining a lane is costlier than
            // an incidental shared key between unrelated dense rows.
            const double stroke=pressure*(isolated+1.22*chain);
            jackSquares+=stroke*stroke;
            freshNotes+=1.-.77*ramp(pressure*(.24+.45*adjacent+.61*chain));
            prior[k]=last[k];last[k]=f.t;
        }
        const int width=motorPop(f.keys);
        bin[v47::MNotes]+=freshNotes*(.72+.28/width)*(1.-.65*ramp(split));
        bin[v47::MJack]+=std::sqrt(jackSquares);
        // An unrelated strike between two grips does not release their anchor.
        // Parallel surviving anchors describe one change, so use its largest
        // contribution once. This also makes the result independent of lane order.
        double chord=0.;
        for(int k=0;k<7;++k) {
            auto& track=anchors[k];
            if(!(f.keys&(1u<<k))) {
                if(f.keys&track.previous)track=AnchorTrack{};
                continue;
            }
            auto grip=f;grip.gap=std::max(.001,f.t-track.time);
            chord=std::max(chord,track.omissions.update(grip,track.previous));
            track.previous=f.keys;track.time=f.t;
        }
        bin[v47::MChord]+=chord;
        bin[v47::MDelay]+=split;
        bin[v47::MTech]+=technicalEffort(h,i,learned[i]);
        bin[v47::MStamina]+=width*(.68+.32/width);
    }
    const auto rate=[&](int axis) {
        auto a=v47::summarizeMotor(bins,axis);
        return .18*a[0]+.50*a[1]+.32*a[2];
    };
    auto notes=v47::summarizeMotor(bins,v47::MNotes);
    // Distributed finger work includes lively passages sustained over several
    // bars. A sub-second cluster alone does not describe a chart's NOTES.
    const double stream=.15*notes[0]+.36*notes[1]+.24*notes[2]+.25*notes[4];
    double moving=0.,shortDebt=0.,longDebt=0.,peakDebt=0.;
    const double dt=v47::motorStep;
    const double onset=1.-std::exp(-dt/1.25),slow=1.-std::exp(-dt/24.);
    for(const auto& b:bins) {
        moving+=onset*(b[v47::MStamina]/dt-moving);
        const double work=std::pow(moving/18.,1.65);
        // A pause repays accumulated work, even if a short high-NPS burst
        // immediately precedes it. Both reserves start empty on chart entry.
        const double recovery=1.-std::exp(-dt/(moving<6.?2.5:8.));
        shortDebt+=recovery*(work-shortDebt);
        longDebt+=slow*(work-longDebt);
        peakDebt=std::max(peakDebt,std::sqrt(std::max(0.,longDebt*shortDebt)));
    }
    const double delay=rate(v47::MDelay),jack=rate(v47::MJack);
    const double tech=rate(v47::MTech),chord=rate(v47::MChord);
    return {12.5*std::pow(stream,1.27),720.*std::asinh(delay/13.5),
            68.*std::pow(tech,1.31),720.*std::asinh(jack/15.0),
            134.*chord,400.*peakDebt};
}
}
