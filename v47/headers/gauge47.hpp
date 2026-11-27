#pragma once
#include "gauge_reference.hpp"
#include "reading45.hpp"
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace chart_radar::gauge47 {
// Single-song 7-key original layout. Capacities are simulator units, never Walkure ratings.
enum Field { EasyCap, HardCap, EasySpread, HardSpread, EasyTailRelief, HardTailRelief,
    EasyVsDefault, HardVsDefault, PeakRate, TailRate, RecoveryHeads, EasyPeakEnd,
    HardPeakMin, EasyLateEnd, EasyEarlyEnd, EasyRepayFour, HardPoorBudget,
    EasyPerfectEnd, GainPerHead, PoorLoss, GreatWindow, GoodWindow, GaugeFlags, EndingSpike, EndingLoss, EndingContrast, EndingStart, FieldCount };
inline constexpr std::array<const char*,FieldCount> names={
    "g47_easy_capacity","g47_hard_capacity","g47_easy_phase_spread","g47_hard_phase_spread",
    "g47_easy_tail_relief","g47_hard_tail_relief","g47_easy_vs_default","g47_hard_vs_default",
    "g47_peak_rate","g47_tail_rate","g47_peak_recovery_heads","g47_easy_peak_burst_final",
    "g47_hard_peak_burst_min","g47_easy_late_burst_final","g47_easy_early_burst_final",
    "g47_easy_repay_four","g47_hard_poor_budget","g47_easy_perfect_end",
    "g47_easy_gain_per_head","g47_hard_poor_loss","g47_great_window_ms","g47_good_window_ms","g47_flags","g47_end_spike","g47_end_unrecoverable_loss",
    "g47_end_contrast","g47_end_start_sec"};
using Result=std::array<double,FieldCount>;
struct Rule { double gain, poor; };
inline Rule rule(int heads,int total) {
    return {1.2*total/std::max(heads,1),10.*hardDamageMultiplier(heads,total)};
}
enum Judge { Miss, Bad, Good, Great };
struct Health {
    double easy=20.,hard=100.;
    void success(int n,const Rule& r) {
        easy=std::min(100.,easy+n*r.gain);
        if(hard>=2.)hard=std::min(100.,hard+n*.1);
    }
    void hit(Judge j,const Rule& r) {
        const bool loss=j<=Bad;
        const double increment=j==Miss?-4.8:j==Bad?-3.2:j==Good?.5*r.gain:r.gain;
        easy=std::clamp(easy+increment,2.,100.);
        if(hard<2.)return;
        // The game floors the display to an even percentage before checking <=30.
        const double damage=(hard<32.? .6:1.)*(j==Miss?r.poor:.6*r.poor);
        hard=std::clamp(hard+(loss?-damage:j==Good?.05:.1),0.,100.);
    }
};
inline int poorBudget(const Rule& r) {
    Health gauge; int misses=0;
    while(gauge.hard>=2.){gauge.hit(Miss,r);++misses;}
    return misses-1;
}
struct Head { double time,demand; int lane,row; };
struct Timeline {std::vector<Head> heads; double peak=0.,tail=0.; int peakHead=0, recovery=0,tailHead=0;};
inline Timeline timeline(const DecodedChart& chart,const RadarTempo& tempo) {
    Timeline out;if(chart.notes.empty())return out;
    double main=0.;std::vector<double> scroll;
    if(!chart.changes.empty())v45::measureReading(chart,v37::timeline(chart,tempo,main),&scroll);
    const double origin=chart.notes.front().start;
    std::array<double,8> last,end;
    last.fill(-1.e6);end.fill(-1.e6);
    std::array<double,2> hand{};
    double spanLoad=0.,shortLoad=0.,prev=-10.,lastGap=.1;
    int rowNumber=0;
    for(size_t start=0; start<chart.notes.size();){
        size_t stop=start+1;double t=chart.notes[start].start;
        while(stop<chart.notes.size()&&chart.notes[stop].start==t)++stop;
        const double gap=std::max(0.,t-prev);
        bool hasHead=false;
        for(size_t i=start;i<stop;++i){const auto& n=chart.notes[i];if(n.lane>=0 && n.lane<8 && n.start>end[n.lane]){hasHead=true;break;}}
        if(!hasHead){start=stop;continue;}
        const double quickDecay=std::exp(-gap/.50);shortLoad*=quickDecay;
        spanLoad*=std::exp(-gap/5.);
        for(double& h:hand)h*=quickDecay;
        double rowLoad=0.;
        std::array<int,8> lane{};std::array<double,8> repetition{};int count=0;
        // On a 1P scratch-left layout, use the less loaded hand for the middle key.
        int middle=hand[0]<=hand[1]?0:1;
        for(size_t i=start;i<stop;++i){
            const auto& n=chart.notes[i];const int k=n.lane;
            if(k<0||k>=8||n.start<=end[k])continue;
            end[k]=n.end;
            int side=k==7||k<3?0:k==3?middle:1;
            const double since=t-last[k];last[k]=t;
            // Finite intervals below 35 ms do not imply arbitrarily fast voluntary repetitions.
            const double same=1./std::max(.035,since);
            lane[count]=k;repetition[count]=same;++count;
            const double effort=k==7?1.38:1.;
            hand[side]+=effort;rowLoad+=effort;
        }
        if(count){
            shortLoad+=rowLoad;spanLoad+=rowLoad;
            const double local=(shortLoad-.5*rowLoad)/.5;
            const double imbalance=2.*std::max(hand[0],hand[1])/std::max(1.,hand[0]+hand[1])-1.;
            const int second=std::max(0,int(t-origin));
            double read=second<int(scroll.size())?scroll[second]:0.;
            double hold=0.;for(double ends:end)hold+=ends>t+.015;
            const double irregular=std::min(1.,std::abs(gap-lastGap)/std::max(.04,gap));
            const double shared=local*(1.+.18*imbalance)+.20*(spanLoad/5.)+.18*read+.16*hold;
            for(int i=0;i<count;++i){
                const double repeat=std::max(0.,repetition[i]-4.);
                double demand=std::max(1.,shared+.70*repeat+.12*local*irregular);
                out.heads.push_back({t-origin,demand,lane[i],rowNumber});
            }
            ++rowNumber;lastGap=gap;prev=t;
        }
        start=stop;
    }
    if(out.heads.empty())return out;
    // Highest four-second interval, weighted by the number of actions in it.
    const double lastT=out.heads.back().time;double integral=0.;size_t left=0;
    for(size_t j=0;j<out.heads.size();++j){
        const Head& h=out.heads[j];integral+=h.demand;
        while(left<j && h.time-out.heads[left].time>=4.)integral-=out.heads[left++].demand;
        if(integral>out.peak){
            out.peak=integral;out.peakHead=int(left+(j-left)/2);out.recovery=int(out.heads.size()-j-1);
        }
        if(h.time>=lastT-8.)out.tail=std::max(integral,out.tail);
    }
    out.peak/=4.;out.tail/=4.;
    out.tailHead=int(std::lower_bound(out.heads.begin(),out.heads.end(),lastT-8.,
                      [](const Head& h,double t){return h.time<t;})-out.heads.begin());
    return out;
}
inline uint32_t mix(uint32_t x) {
    x^=x>>16;x*=0x7feb352dU;x^=x>>15;x*=0x846ca68bU;return x^(x>>16);
}
inline double shock(uint32_t k) {return -std::log((double(mix(k))+.5)/4294967296.);}
struct Threshold {double great,good,contact;};
inline std::vector<Threshold> thresholds(const Timeline& t,int phase,double greatMs,double goodMs) {
    std::vector<Threshold> result;result.reserve(t.heads.size());
    const uint32_t salt=uint32_t(phase+1)*0x9e3779b9U;
    for(size_t i=0;i<t.heads.size();++i){
        const Head& h=t.heads[i];
        // Nearby notes share a temporary loss of timing. Simultaneous notes also share a row shock.
        double block=shock(salt^(uint32_t(std::floor((h.time+.13*phase)/.44))*2654435761U));
        double row=shock((salt+314159U)^uint32_t(h.row));
        double key=shock((salt+271828U)^uint32_t(i));
        double jitter=h.demand*(7.+11.*block+9.*row+11.*key);
        double contact=h.demand*(.11+.13*block+.13*row+.18*key);
        result.push_back({std::max(contact,jitter/greatMs),std::max(contact,jitter/goodMs),contact});
    }
    return result;
}
using Six=std::array<double,6>;
inline Six outcomes(const std::vector<Threshold>& scores,double cap,const Rule& r,const Rule& nominal,int tail){
    Health a,b,prefix;int run=0;
    for(int i=0;i<int(scores.size());++i){
        if(i==tail){prefix=a;prefix.success(run,r);}
        const auto& s=scores[i];if(cap>=s.great){++run;continue;}
        if(run){a.success(run,r);b.success(run,nominal);run=0;}
        const Judge j=cap<s.contact?Miss:cap<s.good?Bad:Good;
        a.hit(j,r);b.hit(j,nominal);
    }
    a.success(run,r);b.success(run,nominal);prefix.success(int(scores.size())-tail,r);
    return {a.easy-80.,a.hard-2.,b.easy-80.,b.hard-2.,prefix.easy-80.,prefix.hard-2.};
}
inline Six required(const std::vector<Threshold>& hits,const Rule& r,const Rule& nominal,int tail){
    // Re-evaluate all six counterfactuals with the same sequence and clearance ladder.
    // The last observed failure handles the HARD low-life discontinuity.
    double perfect=1.;for(const auto& h:hits)perfect=std::max(perfect,h.great);
    Six result{},lastMargin{};std::array<bool,6> lastFailure{};
    double previous=0.;int passRun=0;
    for(double trial=1.; ;trial*=1.095){
        double cap=std::min(trial,perfect);
        const auto margins=outcomes(hits,cap,r,nominal,tail);
        bool all=true;
        for(int g=0;g<6;++g){
            if(margins[g]<0.){lastFailure[g]=true;result[g]=cap;all=false;}
            else if(lastFailure[g]){
                const double frac=-lastMargin[g]/std::max(1.e-9,margins[g]-lastMargin[g]);
                result[g]=previous+std::clamp(frac,0.,1.)*(cap-previous);
                lastFailure[g]=false;
            }
        }
        passRun=all?passRun+1:0;
        // Ten consecutive successes span more than a factor of two in ability.
        if(cap>=perfect||passRun>=10)break;
        lastMargin=margins;previous=cap;
    }
    return result;
}
inline std::pair<double,double> burst(int n,int at,const Rule& r) {
    // At most eight errors, fixed order and mix, all other notes are GREAT.
    int count=std::min(8,n);int begin=std::clamp(at,0,n-count);Health q;q.success(begin,r);
    for(int i=0;i<count;++i)q.hit(i%3==0?Miss:Bad,r);
    const double lowest=q.hard;q.success(n-begin-count,r);return {q.easy,lowest};
}
// These fixed independent quantiles marginalize the same transient, row and key shocks
// used in the scenarios. They keep END SPIKE independent of the three particular seeds.
inline double radicalInverse(int n,int base) {
    double v=0.,weight=1./base;
    while(n){v+=(n%base)*weight;n/=base;weight/=base;}
    return v;
}
struct Ending { bool spike=false; double shortfall=0.,contrast=0.,at=-1.; };
inline Ending ending(const Timeline& t,double cap,const Rule& r,double greatMs,double goodMs) {
    Ending answer;const double duration=t.heads.back().time;
    if(duration<12. || cap<=0.)return answer;
    std::array<std::array<double,64>,3> levels;
    for(int i=0;i<64;++i){
        const double block=-std::log(radicalInverse(i+1,2));
        const double row=-std::log(radicalInverse(i+1,3));
        const double key=-std::log(radicalInverse(i+1,5));
        const double jitter=7.+11.*block+9.*row+11.*key;
        levels[0][i]=.11+.13*block+.13*row+.18*key;
        levels[1][i]=std::max(levels[0][i],jitter/goodMs);
        levels[2][i]=std::max(levels[0][i],jitter/greatMs);
    }
    for(auto& l:levels)std::sort(l.begin(),l.end());
    const int length=int(std::floor(duration*2.))+1;
    std::vector<double> loss(length+1),load(length+1);std::vector<int> count(length+1);
    for(const auto& head:t.heads){
        const double speed=cap/head.demand;
        std::array<double,3> p;
        for(int g=0;g<3;++g)p[g]=(levels[g].end()-std::upper_bound(levels[g].begin(),levels[g].end(),speed))/64.;
        double misses=p[0],bads=p[1]-misses,goods=p[2]-p[1],greats=1.-p[2];
        const int bin=int(head.time*2)+1;
        loss[bin]+=4.8*misses+3.2*bads-r.gain*(greats+.5*goods);
        load[bin]+=head.demand; ++count[bin];
    }
    for(int i=1;i<=length;++i){loss[i]+=loss[i-1];load[i]+=load[i-1];count[i]+=count[i-1];}
    // An end window must finish in the final fifth and final 20 s, and its own
    // motor work must stand out from earlier occupied windows at the same scale.
    const int tail=std::max(int(length*.80),length-40);
    for(int width:{4,8,16,24}){
        if(tail<2*width)continue;
        std::vector<double> earlier;
        for(int j=width;j<=tail;++j)if(count[j]!=count[j-width])earlier.push_back(load[j]-load[j-width]);
        if(earlier.empty())continue;
        auto q=earlier.begin()+size_t(.9*(earlier.size()-1));std::nth_element(earlier.begin(),q,earlier.end());
        for(int j=std::max(tail+width/2,width);j<=length;++j){
            double contrast=(load[j]-load[j-width])/std::max(1.,*q);
            double fall=std::clamp(loss[j]-loss[j-width],0.,98.);
            // Enter full, lose this amount in the candidate window, then recover
            // every remaining judgment as GREAT. More than 20 pp still missing
            // means even that suffix cannot reach the 80% border.
            double deficit=std::max(0.,fall-(count.back()-count[j])*r.gain);
            if(contrast>=1.20 && deficit>answer.shortfall){
                answer.shortfall=deficit;answer.contrast=contrast;answer.at=.5*(j-width);
            }
        }
    }
    answer.spike=answer.shortfall>20.;
    return answer;
}

inline Result measure(const DecodedChart& chart,const RadarTempo& timing){
    Result f{};const auto t=timeline(chart,timing);int n=int(t.heads.size());if(!n)return f;
    const int normal=int(defaultGaugeTotal(n)),total=chart.total>=1.?int(chart.total):normal;
    const Rule actual=rule(n,total),nominal=rule(n,normal);
    const int rank=chart.judgeRank>=0&&chart.judgeRank<=3?chart.judgeRank:2;
    constexpr double greatMs[]={24,30,40,60},goodMs[]={40,60,100,120};
    std::array<Six,3> tests;
    for(int p=0;p<3;++p)tests[p]=required(thresholds(t,p,greatMs[rank],goodMs[rank]),actual,nominal,t.tailHead);
    Six med{};
    for(int g=0;g<6;++g)med[g]=std::max(std::min(tests[0][g],tests[1][g]),std::min(std::max(tests[0][g],tests[1][g]),tests[2][g]));
    f[EasyCap]=med[0];f[HardCap]=med[1];
    for(int g=0;g<2;++g)f[EasySpread+g]=std::max({tests[0][g],tests[1][g],tests[2][g]})-std::min({tests[0][g],tests[1][g],tests[2][g]});
    f[EasyTailRelief]=med[0]-med[4];f[HardTailRelief]=med[1]-med[5];
    f[EasyVsDefault]=med[0]-med[2];f[HardVsDefault]=med[1]-med[3];
    f[PeakRate]=t.peak;f[TailRate]=t.tail;f[RecoveryHeads]=t.recovery;
    auto peak=burst(n,t.peakHead-4,actual);
    f[EasyPeakEnd]=peak.first;f[HardPeakMin]=peak.second;
    f[EasyLateEnd]=burst(n,n-8,actual).first;f[EasyEarlyEnd]=burst(n,n/8,actual).first;
    f[EasyRepayFour]=std::ceil(19.2/actual.gain);f[HardPoorBudget]=poorBudget(actual);
    f[EasyPerfectEnd]=std::min(100.,20.+actual.gain*n);f[GainPerHead]=actual.gain;f[PoorLoss]=actual.poor;
    f[GreatWindow]=greatMs[rank];f[GoodWindow]=goodMs[rank];
    int flags=0;const double defaultRepay=std::ceil(19.2/nominal.gain);
    if(total<50)flags|=1;
    if(f[HardPoorBudget]==0 && poorBudget(nominal)>0)flags|=2;
    if(f[HardPoorBudget]*2<poorBudget(nominal))flags|=4;
    if(f[EasyRepayFour]>=2*defaultRepay)flags|=8;
    if(f[EasyRepayFour]*2<=defaultRepay)flags|=16;
    if(std::abs(f[EasyVsDefault])>=std::max(2.,.12*med[2]) ||
       std::abs(f[HardVsDefault])>=std::max(2.,.12*med[3]))flags|=32;
    f[GaugeFlags]=double(flags);
    const auto end=ending(t,med[0],actual,greatMs[rank],goodMs[rank]);
    f[EndingSpike]=end.spike;f[EndingLoss]=end.shortfall;f[EndingContrast]=end.contrast;f[EndingStart]=end.at;
    return f;
}
// Level 2 can cross the 80% border from full; level 1 tests entering at 90%.
// A 90%-entry warning also needs a measurable final-eight-second capacity penalty.
inline int endingRisk(const Result& f) {
    if(f[EndingSpike]>.5)return 2;
    const double margin=std::max(.10*f[EasyCap],.5*f[EasySpread]);
    return (f[EndingLoss]>10. && f[EasyTailRelief]>margin)?1:0;
}

}
