#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <numeric>
#include <vector>

namespace chart_radar::v47 {

using PressureRow = std::array<double,8>;
using HumanFeatures = std::array<std::array<double,10>,8>;
constexpr double motorStep = .25;
enum MotorAxis { MNotes, MDelay, MScratch, MScroll, MJack, MTech, MChord, MStamina };

inline int motorPop(unsigned x) {
    int n=0;
    for(;x;x&=x-1)++n;
    return n;
}
inline double ramp(double x) { return std::clamp(x,0.,1.); }
inline double urgency(double gap,double start,double full) {
    return ramp((start-gap)/(start-full));
}
// Pressure grows when less time is available to release and actuate the same finger.
inline double repress(double gap) {
    return urgency(gap,.31,.13)*std::pow(.14/std::max(.034,gap),.8);
}
inline double gripCenter(unsigned x) {
    double sum=0.;
    for(int k=0;k<7;++k)if(x&(1u<<k))sum+=k;
    return sum/std::max(1,motorPop(x));
}
struct HandBeat {
    double time,gap;
    unsigned keys,full;
};
struct MotorHand {
    std::array<HandBeat,24> history{};
    int count=0;
    std::array<double,7> last{};
    MotorHand() {last.fill(-100.);}
    const HandBeat& back(int n) const {return history[(count-1-n)%int(history.size())];}
    bool learned(unsigned keys,double gap) const {
        for(int period=1;period<=6;++period){
            if(count<2*period)continue;
            if(back(period-1).keys!=keys || std::abs(gap-back(period-1).gap)>.012)continue;
            bool repeats=true;
            for(int k=0;k<period;++k){
                if(back(k).keys!=back(k+period).keys ||
                   std::abs(back(k).gap-back(k+period).gap)>.012){repeats=false;break;}
            }
            if(repeats)return true;
        }
        return false;
    }
    // Jack, technical, motor work for this hand. All input is time and physical onsets.
    std::array<double,3> strike(double t,unsigned keys,unsigned full,unsigned held) {
        if(!keys)return {};
        const int width=motorPop(keys);
        const double gap=count?t-back(0).time:10.;
        const unsigned prev=count?back(0).keys:0;
        const double fast=urgency(gap,.26,.072);
        double jack=0.,tech=0.;
        if(count){
            const unsigned overlap=keys&prev;
            const unsigned changed=keys^prev;
            const bool moved=changed!=0;
            const int common=motorPop(overlap);
            // Two or more of the same fingers repeating together form a chordjack,
            // even if a hand cut happens to assign one of them to each hand.
            const bool repeatingGrip=motorPop(full&back(0).full)>=2;
            if(!moved && width==1 && !repeatingGrip)jack=repress(gap);
            if(moved){
                const double tempoChange=urgency(back(0).gap,.28,.095)*
                    ramp((std::abs(gap-back(0).gap)-.012)/.09);
                const double swap=double(motorPop(changed))/motorPop(keys|prev);
                const double anchoring=common*swap*(width>1||motorPop(prev)>1);
                const double shape=(width>1||motorPop(prev)>1)?swap:0.;
                const bool otherChanges=(full&~keys)!=(back(0).full&~prev);
                const double heldConflict=motorPop(held&~keys)*.30;
                const double familiar=learned(keys,gap)?.35:1.;
                double returning=0.,reversal=0.;
                for(int k=0;k<7;++k)if((keys&(1u<<k))&&!(prev&(1u<<k)))
                    returning+=repress(t-last[k]);
                if(count>=2 && keys!=back(1).keys){
                    double oldMotion=gripCenter(prev)-gripCenter(back(1).keys);
                    double motion=gripCenter(keys)-gripCenter(prev);
                    if(oldMotion*motion<0.)reversal=ramp(std::min(std::abs(oldMotion),std::abs(motion))/2.);
                }
                tech=fast*(.95*anchoring+.38*shape+.55*tempoChange+.38*shape*otherChanges+
                    familiar*(.70*returning+.52*reversal)+heldConflict);
            } else if(width==1 && count>=2 && back(1).keys!=keys){
                // The first repeat after a change of finger is the short embedded jack.
                tech=fast*urgency(back(0).gap,.22,.075)*.75;
            }
        }
        for(int k=0;k<7;++k)if(keys&(1u<<k))last[k]=t;
        history[count%int(history.size())]={t,gap,keys,full};++count;
        const double effort=width+.12*(width-1)*(width-1)+fast*.18*width;
        return {jack,tech,effort};
    }
};

inline std::array<double,10> summarizeMotor(const std::vector<PressureRow>& bins,int a) {
    std::array<double,10> result{};
    const size_t n=bins.size();
    if(!n)return result;
    std::vector<double> prefix(n+1),shortRates(n);
    double fastHistory=0.,slowHistory=0.,squares=0.,lastEpisode=0.,currentEpisode=0.;
    int quiet=10000;
    auto rate=[&](size_t end,size_t width) {
        const size_t begin=end>width?end-width:0;
        return (prefix[end]-prefix[begin])/(motorStep*width);
    };
    const double fastDecay=std::exp(-motorStep/1.5),slowDecay=std::exp(-motorStep/12.);
    for(size_t i=0;i<n;++i){
        const double v=bins[i][a],instant=v/motorStep;
        prefix[i+1]=prefix[i]+v;
        std::array<size_t,4> widths={3,12,40,120};
        for(int k=0;k<4;++k)result[k]=std::max(result[k],rate(i+1,widths[k]));
        shortRates[i]=rate(i+1,12);squares+=shortRates[i]*shortRates[i];
        fastHistory=fastDecay*fastHistory+(1.-fastDecay)*instant;
        // Previous pressure matters before the motor system has recovered.
        result[6]=std::max(result[6],std::sqrt(std::max(0.,fastHistory*slowHistory)));
        slowHistory=slowDecay*slowHistory+(1.-slowDecay)*instant;
        if(v>0.){
            if(quiet>=2){
                const double residual=lastEpisode*std::exp(-motorStep*quiet/3.);
                result[8]=std::max(result[8],std::sqrt(std::max(0.,fastHistory*residual)));
                currentEpisode=0.;
            }
            quiet=0;currentEpisode=std::max(currentEpisode,fastHistory);
        } else {
            if(quiet==0)lastEpisode=currentEpisode;
            ++quiet;
        }
        if(n-i<=48)result[9]=std::max(result[9],shortRates[i]);
    }
    const size_t top=std::max(size_t(1),(n+9)/10);
    auto cut=shortRates.end()-top;std::nth_element(shortRates.begin(),cut,shortRates.end());
    result[4]=std::accumulate(cut,shortRates.end(),0.)/top;
    result[5]=std::sqrt(squares/n);result[7]=prefix.back();
    return result;
}

// Frames provide t, keys, holds and scratch from the 7-key native timeline.
// actualScroll contains the v45 effective-motion dose per one-second bin.
template<class Frame>
inline HumanFeatures humanMechanics(const std::vector<Frame>& frames,const std::vector<double>& actualScroll,
                                   std::vector<PressureRow>* evidence=nullptr) {
    HumanFeatures result{};
    if(frames.empty())return result;
    const size_t n=size_t(frames.back().t/motorStep)+1;
    std::vector<PressureRow> bins(n);
    std::array<std::vector<std::array<double,3>>,2> options;
    for(auto& p:options)p.resize(n);
    std::array<std::array<MotorHand,2>,2> hands;
    std::vector<double> scrollHeads(actualScroll.size());
    for(const auto& f:frames){
        size_t s=size_t(f.t);
        if(s<scrollHeads.size())scrollHeads[s]+=motorPop(f.keys)+int(f.scratch);
    }
    unsigned previous=0,priorChord=0,priorPriorChord=0,prevVisual=0;
    double keyTime=-100.,lastGap=10.,chordTime=-100.,priorChordTime=-100.;
    double deckTime=-100.,previousDeckGap=10.,visualTime=-100.;
    for(const auto& f:frames){
        const double t=f.t;const unsigned mask=unsigned(f.keys)&127u;
        const size_t b=std::min(n-1,size_t(t/motorStep));auto& row=bins[b];
        const int width=motorPop(mask);
        row[MNotes]+=width;
        if(f.scratch){
            const double gap=t-deckTime;
            const double shortGap=repress(gap);
            const double irregular=ramp((std::abs(gap-previousDeckGap)-.02)/.14)*urgency(previousDeckGap,.45,.17);
            row[MScratch]+=.55+shortGap*(.75+.32*irregular)+
                .22*width+.17*motorPop(unsigned(f.holds)&~mask);
            deckTime=t;previousDeckGap=gap;
        }
        const unsigned visualMask=mask|(f.scratch?128u:0u);
        const size_t second=size_t(t);
        if(second<actualScroll.size() && scrollHeads[second]>0. && visualMask){
            double change=double(motorPop(visualMask^prevVisual))/std::max(1,motorPop(visualMask|prevVisual));
            double choice=1.+.13*std::max(0,motorPop(visualMask)-1);
            row[MScroll]+=actualScroll[second]/scrollHeads[second]*choice*
                (.62+.38*change*urgency(t-visualTime,.35,.065));
        }
        prevVisual=visualMask;visualTime=t;
        if(!mask)continue;
        const double gap=t-keyTime;
        if(previous && mask!=previous && gap>1e-6 && gap<.085) {
            const double separation=urgency(gap,.085,.033);
            const double group=ramp((lastGap/gap-1.)/3.);
            row[MDelay]+=separation*(.065/std::max(.022,gap))*(.65+.35*group);
        }
        if(width>=2){
            const int common=motorPop(mask&priorChord);
            const double shared=common/double(std::max(width,motorPop(priorChord)));
            double demand=repress(t-chordTime)*(width-1)*shared;
            if(priorPriorChord==mask && !common)
                demand+=.30*repress(t-priorChordTime)*(width-1);
            row[MChord]+=demand;
            priorPriorChord=priorChord;priorChordTime=chordTime;
            priorChord=mask;chordTime=t;
        }
        for(int assignment=0;assignment<2;++assignment){
            const unsigned left=assignment?15u:7u;
            auto& o=options[assignment][b];double effort[2]{};
            for(int side=0;side<2;++side){
                const unsigned fingers=side?(127u^left):left;
                auto demand=hands[assignment][side].strike(t,mask&fingers,mask,unsigned(f.holds)&fingers);
                o[0]+=demand[0];o[1]+=demand[1];effort[side]=demand[2];
            }
            o[2]+=std::max(effort[0],effort[1])+.38*std::min(effort[0],effort[1]);
        }
        previous=mask;lastGap=gap;keyTime=t;
    }
    // A fixed fingering for the entire chart, independently evaluated per skill.
    // Moving the centre key from hand to hand on every note would understate work.
    for(int j=0;j<3;++j){
        std::array<double,2> burden{};
        for(int a=0;a<2;++a)for(const auto& x:options[a])burden[a]+=x[j]*x[j];
        const int side=burden[1]<burden[0];const int axis=j==0?MJack:j==1?MTech:MStamina;
        const bool equal=std::abs(burden[1]-burden[0])<=1.e-10*std::max({1.,burden[0],burden[1]});
        double reserve=0.;const double decay=std::exp(-motorStep/7.);
        for(size_t i=0;i<n;++i){
            double v=equal?.5*(options[0][i][j]+options[1][i][j]):options[side][i][j];
            if(axis==MStamina){
                // Motor effort after repeated activation; recovery proceeds throughout rests.
                bins[i][axis]=std::sqrt(std::max(0.,v*reserve*motorStep));
                reserve=decay*reserve+(1.-decay)*v/motorStep;
            } else bins[i][axis]=v;
        }
    }
    for(int a=0;a<8;++a)result[a]=summarizeMotor(bins,a);
    if(evidence)evidence->swap(bins);
    return result;
}
}
