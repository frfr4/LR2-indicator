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

struct HandRow {double time;unsigned keys,opposite;int bin;};

// Read each hand's own note sequence. An intervening opposite-hand hit does not
// end a minijack, and a held anchor can sit inside a repeating chord pattern.
inline void handLoad(const std::vector<HandRow>& rows,std::vector<double>& work) {
    std::array<int,7> lastIndex,run;lastIndex.fill(-1);run.fill(1);
    std::array<double,7> burst{};std::array<bool,7> varied{};
    const auto finish=[&](int k,int end) {
        if(run[k]>=2&&run[k]<=4 && end>=0 && varied[k])
            work[rows[end].bin]+=burst[k];
    };
    double prevMotion=0.,prevGap=1.;
    for(int i=0;i<int(rows.size());++i) {
        const auto& row=rows[i];const unsigned keys=row.keys;
        const unsigned prev=i?rows[i-1].keys:0,opp=i?rows[i-1].opposite:0;
        const double gap=i?row.time-rows[i-1].time:1.;
        const double fast=unit((.24-gap)/.16);
        const unsigned common=keys&prev;
        for(int k=0;k<7;++k)if(keys&(1u<<k)) {
            const int j=lastIndex[k];
            const double dt=j>=0?row.time-rows[j].time:1.;
            if(dt>=.018 && dt<=.172) {
                ++run[k];burst[k]+=unit((.195-dt)/.125);
                varied[k]|=i-j>1||keys!=rows[j].keys||row.opposite!=rows[j].opposite;
            } else {
                if(j>=0 && j+1<i && rows[j+1].time-rows[j].time<.19) varied[k]|=rows[j+1].keys!=rows[j].keys;
                finish(k,j);run[k]=1;burst[k]=0.;
                varied[k]=i>0 && gap<.19 && keys!=prev;
            }
            lastIndex[k]=i;
        }
        if(i && keys!=prev) {
            const auto center=[](unsigned mask){int sum=0;for(int k=0;k<7;++k)if(mask&(1u<<k))sum+=k;return double(sum)/fingers(mask);};
            const double motion=center(keys)-center(prev);
            const bool grip=std::max(fingers(keys),fingers(prev))>=2;
            const double anchor=grip && common?fast*fingers(keys^prev)/double(fingers(keys|prev)):0.;
            // A changing multi-key grip against another changing hand, including
            // asymmetric repeating trills that stay physically awkward after learning.
            const double asymmetric=grip && (row.opposite||opp) && row.opposite!=opp?
                fast*unit((fingers(keys^prev)-1)/2.)*(row.opposite?.95:.42):0.;
            const bool turns=i>=2 && keys!=rows[i-2].keys && motion*prevMotion<0.;
            const double reversal=turns?unit((.23-std::max(gap,prevGap))/.17)*unit(std::min(std::abs(motion),std::abs(prevMotion))/2.):0.;
            const double split=(gap>=.014 && gap<.066 && i>=2)?
                unit((prevGap/std::max(.014,gap)-1.38)/1.8)*unit((.078-gap)/.046):0.;
            work[row.bin]+=1.25*anchor+1.65*asymmetric+.60*reversal+.85*split;
            prevMotion=motion;
        } else prevMotion=0.;
        prevGap=gap;
    }
    for(int k=0;k<7;++k)finish(k,lastIndex[k]);
}

// Very close, separate key onsets form a staggered chord when interleaved
// with changing grips. A uniform split with the same keys and timing is learned.
inline void addSplitChords(const std::vector<HandRow>& rows,std::vector<Scores>& bins) {
    unsigned previous=0;double previousEnd=-10.;int previousCount=0;
    for(size_t i=0;i<rows.size();) {
        size_t j=i+1;unsigned keys=rows[i].keys;double gaps=0.;bool doubles=fingers(keys)>1;
        while(j<rows.size() && rows[j].time-rows[j-1].time<=.026 && rows[j].time-rows[i].time<=.072) {
            keys|=rows[j].keys;doubles|=fingers(rows[j].keys)>1;
            gaps+=rows[j].time-rows[j-1].time;++j;
        }
        const int n=int(j-i);
        if(n>=2 && fingers(keys)>=2 && i && j<rows.size()) {
            const double dt=gaps/(n-1);
            const double lead=rows[i].time-previousEnd,follow=rows[j].time-rows[j-1].time;
            // Require a gap boundary and a switch in grip or grouping context.
            // Avoid classifying an uninterrupted fast single-key roll as a split chord.
            const double boundary=unit((std::max(lead,follow)/std::max(.006,dt)-1.65)/2.0);
            const double crowd=unit((.24-std::min(lead,follow))/.16);
            const bool changed=keys!=previous||n!=previousCount;
            const double difficulty=changed?(.65+.25*doubles+.20*bool(keys&previous)):0.;
            const double tight=unit((.032-dt)/.022);
            bins[rows[i].bin][Tech]+=4.0*(n-1)*boundary*crowd*difficulty*tight;
        }
        previous=keys;previousCount=n;previousEnd=rows[j-1].time;i=j;
    }
}

inline void addHandSections(const std::vector<HandRow>& global,std::vector<Scores>& bins) {
    std::array<std::vector<double>,2> profile;
    for(int cut=3;cut<=4;++cut) {
        auto& w=profile[cut-3];w.assign(bins.size(),0.);
        const unsigned left=(1u<<cut)-1;
        for(unsigned side:{left,127u^left}){
            std::vector<HandRow> rows;rows.reserve(global.size());
            for(auto r:global)if(r.keys&side)rows.push_back({r.time,r.keys&side,r.keys&(127u^side),r.bin});
            handLoad(rows,w);
        }
    }
    for(size_t b=0;b<bins.size();++b){
        const size_t next=std::min(b+1,bins.size()-1);
        const int easier=profile[1][b]+profile[1][next]<profile[0][b]+profile[0][next]?1:0;
        bins[b][Tech]+=profile[easier][b];
    }
}

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
    std::vector<HandRow> keyRows;
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
        keyRows.push_back({t,mask,0,std::clamp(int(t),0,bins-1)});
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
    addHandSections(keyRows,events);
    addSplitChords(keyRows,events);
    // Allocate reading strain in the seconds affected by an actual speed change or STOP.
    for(const auto& change:chart.changes) {
        double t=change.time-origin;
        const double delta=std::abs(std::log2(std::clamp(change.ratio,1./64.,64.)))+
                           std::min(4.,2.*change.stop)+(change.reversal?2.:0.);
        if(delta<1e-6)continue;
        if(t>=0 && t<=span)out.lastChange=std::max(out.lastChange,t);
        for(int b=std::max(0,int(std::floor(t))-1);b<std::min(bins,int(std::floor(t))+4);++b) {
            const double proximity=std::max(0.,1.-std::abs((b+.5)-t)/3.5);
            events[b][Soflan]+=std::log1p(events[b][Density]+events[b][Scratch])*delta*proximity;
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
