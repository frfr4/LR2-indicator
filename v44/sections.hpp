#pragma once
#include "v40_scores.hpp"
#include "gauge_reference.hpp"

namespace chart_radar::v44 {
struct Sections {
    Scores dose{}, peak{}, peakTime{}, sustained{};
    double duration=0., heads=0., total=0., normalTotal=0., poor=0., typicalPoor=0.;
    double lastChange=-1., afterDensity=0., endDensity=0., avgDensity=0.;
    int gaugeFlags=0;
};
inline int fingers(unsigned mask) { return int(std::bitset<8>(mask).count()); }
inline double unit(double x) { return std::clamp(x,0.,1.); }
inline Sections measure(const DecodedChart& chart,const RadarTempo& timing) {
    Sections out;
    if(chart.notes.empty())return out;
    const double origin=chart.notes.front().start;
    const double span=chart.notes.back().start-origin;
    if(!std::isfinite(span)||span<0.||span>86400.)throw std::invalid_argument("invalid chart duration");
    out.duration=span;
    const int bins=1+int(std::floor(span));
    std::vector<Scores> events(bins);
    std::array<double,7> last{},held{};last.fill(-100.);held.fill(-100.);
    std::array<int,7> lastRow{};lastRow.fill(-100);
    std::array<double,7> priorGap{};priorGap.fill(1.);
    unsigned prev=0,prev2=0,prevChord=0;double prevTime=-100.,prevGap=1.,chordTime=-100.,scratchTime=-100.;
    std::array<unsigned,16> history{};std::array<double,16> rhythm{};
    std::array<int,9> matching{};
    int row=0,keysTotal=0;
    for(size_t p=0;p<chart.notes.size();) {
        const double t=chart.notes[p].start-origin;
        unsigned mask=0;bool scratch=false;std::array<double,7> ends{};
        while(p<chart.notes.size() && chart.notes[p].start-origin<=t+1e-7) {
            const auto& n=chart.notes[p++];
            if(n.lane==7)scratch=true;
            else if(n.lane>=0&&n.lane<7) { mask|=1u<<n.lane;ends[n.lane]=n.end-origin; }
        }
        Scores& w=events[std::clamp(int(t),0,bins-1)];
        const int width=fingers(mask);
        if(scratch){w[Scratch]+=1.+unit((.33-(t-scratchTime))/.26);scratchTime=t;}
        if(!mask)continue;
        keysTotal+=width;w[Density]+=width;
        const double gap=t-prevTime;const double fast=unit((.21-gap)/.15);
        double quickReturn=0.,fixedFinger=0.,heldWork=0.;
        for(int k=0;k<7;++k) {
            if(held[k]>t+.005 && (mask&~(1u<<k)))heldWork=1.;
            if(!(mask&(1u<<k)))continue;
            const double dt=t-last[k];
            if(dt>.0001 && lastRow[k]>=0) {
                const int apart=row-lastRow[k];
                const double sameFinger=unit((.235-dt)/.17);
                if(apart==1 && width==1)
                    w[Jack]+=sameFinger*(.12/std::max(.025,dt))*(prev==(1u<<k)?1.:.55);
                if(mask!=prev && (apart==2||apart==3))quickReturn+=sameFinger;
                if(apart==1 && mask!=prev && (width>1||fingers(prev)>1))
                    fixedFinger+=sameFinger*(.5+.5*unit(std::abs(dt-priorGap[k])/.09));
            }
            last[k]=t;priorGap[k]=dt;lastRow[k]=row;
            if(ends[k]>t)held[k]=ends[k];
        }
        if(width>=2) {
            const double cg=t-chordTime;
            if(cg>0 && cg<.27) {
                const unsigned shared=prevChord&mask;
                const double anchor=fingers(shared)/double(std::min(width,fingers(prevChord)));
                w[Chord]+=(width-1)*unit((.27-cg)/.19)*(.15/std::max(.04,cg))*(.24+.76*anchor);
            }
            prevChord=mask;chordTime=t;
        }
        // A short split or a quick arpeggio along distinct keys makes local delay demand.
        const bool moved=(mask!=prev && prev!=0);
        if(moved && gap>0 && gap<.075) {
            const double separate=unit((.075-gap)/.045);
            w[Stair]+=separate*(.055/std::max(.014,gap))*(1.+.35*unit(std::abs(prevGap-gap)/.045));
        }
        const bool turn=moved && prev2 && mask!=prev2 &&
            ((mask>prev && prev<prev2)||(mask<prev && prev>prev2));
        const double switching=moved && (width>1||fingers(prev)>1)?
            fast*fingers(mask^prev)/4.:0.;
        const double stagger=moved ? fast*unit((std::abs(gap-prevGap)-.012)/.09):0.;
        bool cyclic=false;
        for(int period=1;period<=8;++period){
            const int back=(row+16-period)%16;
            matching[period]=(row>=period && history[back]==mask && std::abs(rhythm[back]-gap)<.009)?matching[period]+1:0;
            if(matching[period]>=2*period)cyclic=true;
        }
        history[row%16]=mask;rhythm[row%16]=gap;
        const double novel=cyclic?0.:(mask!=prev2?1.:.35);
        const double mix=fast*((cyclic?0.:quickReturn*.75)+fixedFinger+novel*(switching+.32*turn+stagger))+heldWork*fast*.45;
        w[Tech]+=mix+(scratch?unit(mix)*.55:0.);
        w[Stamina]+=width+.13*(width-1)*(width-1)+.15*fixedFinger;
        prev2=prev;prev=mask;prevTime=t;prevGap=gap;++row;
    }
    // Allocate reading strain in the seconds affected by an actual speed change or STOP.
    for(const auto& change:chart.changes) {
        double t=change.time-origin;
        const double delta=std::abs(std::log2(std::clamp(change.ratio,1./64.,64.)))+
                           std::min(4.,2.*change.stop)+(change.reversal?2.:0.);
        if(delta<1e-6)continue;
        if(t>=0 && t<=span)out.lastChange=std::max(out.lastChange,t);
        for(int b=std::max(0,int(std::floor(t))-1);b<std::min(bins,int(std::floor(t))+4);++b) {
            const double near=std::max(0.,1.-std::abs((b+.5)-t)/3.5);
            events[b][Soflan]+=std::log1p(events[b][Density]+events[b][Scratch])*delta*near;
        }
    }
    double main=0.;
    const auto frames=v37::timeline(chart,timing,main);
    for(const auto& frame:frames) {
        // Sustained off-main BPM, scroll stops and reversals affect every occupied row.
        const int b=std::clamp(int(frame.t),0,bins-1);
        events[b][Soflan]+=frame.read*(fingers(frame.keys)+int(frame.scratch));
    }
    out.avgDensity=keysTotal/std::max(1.,span);
    for(int axis=0;axis<Count;++axis) {
        std::vector<double> prefix(bins+1);
        for(int i=0;i<bins;++i)prefix[i+1]=prefix[i]+events[i][axis];
        const int shortLen=std::min(bins,axis==Stamina?8:2);
        const int longLen=std::min(bins,axis==Stamina?30:8);
        std::vector<double> loads;loads.reserve(bins);
        for(int i=0;i+shortLen<=bins;++i) {
            const double v=(prefix[i+shortLen]-prefix[i])/shortLen;
            loads.push_back(v);
            if(v>out.peak[axis]){out.peak[axis]=v;out.peakTime[axis]=i;}
            if(axis==Density && out.lastChange>=0 && i>=out.lastChange)out.afterDensity=std::max(out.afterDensity,v);
            if(axis==Density && i+shortLen>=.8*span)out.endDensity=std::max(out.endDensity,v);
        }
        for(int i=0;i+longLen<=bins;++i)out.sustained[axis]=std::max(out.sustained[axis],(prefix[i+longLen]-prefix[i])/longLen);
        const size_t count=std::max(size_t(1),(loads.size()+9)/10);
        std::nth_element(loads.begin(),loads.end()-count,loads.end());
        const double upper=std::accumulate(loads.end()-count,loads.end(),0.)/count;
        if(axis==Stamina)out.dose[axis]=(.35*upper+.65*out.sustained[axis])*std::pow(std::min(360.,std::max(1.,span))/120.,.30);
        else out.dose[axis]=.35*out.peak[axis]+.40*upper+.25*out.sustained[axis];
    }
    if(out.dose[Soflan]>0. && !frames.empty() && main>0.) {
        const auto reading=v37::measureFrames(chart,frames,main);
        const auto across=v37::dose(reading.summary[0][v37::Reading]);
        out.dose[Soflan]=v40::absoluteScore(v37::Reading,across)+6.*std::log1p(out.dose[Soflan]);
    }
    out.heads=gaugeNoteCount(chart);out.normalTotal=defaultGaugeTotal(out.heads);
    out.total=chart.total>0?chart.total:out.normalTotal;
    out.poor=10.*hardDamageMultiplier(int(out.heads),int(out.total));
    out.typicalPoor=10.*hardDamageMultiplier(int(out.heads),int(out.normalTotal));
    if(out.total<.45*out.normalTotal)out.gaugeFlags|=1;
    if(out.poor>=1.75*out.typicalPoor)out.gaugeFlags|=2;
    if(out.total>2.5*out.normalTotal)out.gaugeFlags|=4;
    return out;
}
}
