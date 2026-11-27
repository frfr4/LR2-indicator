"""Install v44 on the pinned and patched v43 source tree."""
from pathlib import Path
import shutil,sys
P=Path(__file__).resolve().parent
def replace(text,old,new):
    if text.count(old)!=1:raise ValueError('Install context is not unique: '+old[:85])
    return text.replace(old,new)
def install(r):
    for name in ['sections.hpp','params.hpp','model44.hpp']:shutil.copyfile(P/name,r/name)
    f=r/'catalog.hpp';s=f.read_text(encoding='utf-8-sig')
    s=replace(s,'#include "tech.hpp"','#include "model44.hpp"').replace('radar_v43_chart','radar_v44_chart').replace('selection_stats_v41','selection_stats_v44')
    s=replace(s,'readTable(path.parent_path()/"charts-v43.tsv",entries,&poor,false);','readTable(path.parent_path()/"charts-v44.tsv",entries,&poor,false);\n        readSummaries(path.parent_path()/"selection-v44.tsv");')
    s=replace(s,'    void openCache(const std::string& path)', '''    std::unordered_map<std::string,int> gaugeKinds;
    std::unordered_map<std::string,double> combinedRatings;
    void readSummaries(const std::filesystem::path& path) {
        std::ifstream f(path);std::string id;v41::SelectionStats row;double easy,hard,rating;int flags;
        while(f>>id>>row.average>>row.maximum>>easy>>hard>>flags>>rating) {
            row.easy=easy;row.hard=hard;statistics.emplace(id,row);gaugeKinds.emplace(id,flags);combinedRatings.emplace(id,rating);
        }
    }
    void openCache(const std::string& path)''')
    s=replace(s,'        auto prior=query(ptr,','''        if(sqlite3_exec(ptr,"CREATE TABLE IF NOT EXISTS gauge_flags_v44(hash TEXT PRIMARY KEY,flags INTEGER)",nullptr,nullptr,nullptr)==SQLITE_OK) {
            auto q=query(ptr,"SELECT hash,flags FROM gauge_flags_v44");
            while(sqlite3_step(q.get())==SQLITE_ROW && sqlite3_column_text(q.get(),0))
                gaugeKinds.emplace(reinterpret_cast<const char*>(sqlite3_column_text(q.get(),0)),sqlite3_column_int(q.get(),1));
        }
        auto oldModes=query(ptr,"SELECT 1 FROM sqlite_master WHERE type='table' AND name='radar_v43_chart'");
        if(sqlite3_step(oldModes.get())==SQLITE_ROW)readCache(ptr,"SELECT * FROM radar_v43_chart WHERE mode<>7",entries);
        auto prior=query(ptr,''')
    s=replace(s,'    std::optional<Scores> find(','''    double patternRating(const std::string& hash,int mode) const {
        std::lock_guard<std::mutex> lock(mutex);auto it=combinedRatings.find(hash);
        return mode==7 && it!=combinedRatings.end()?it->second:0.;
    }
    int gaugeFlags(const std::string& hash,int mode) const {
        std::lock_guard<std::mutex> lock(mutex);
        auto it=gaugeKinds.find(hash);
        return mode==7 && it!=gaugeKinds.end()?it->second:0;
    }
    std::optional<Scores> find(''')
    s=replace(s,'if(auto row=find(hash,mode))return row;','if(auto row=find(hash,mode))return row;\n        if(mode==7)return {};')
    s=replace(s,'if(missingStats)saveStats(hash,mode,v41::summarize(decoded,timing));','''std::optional<v44::Sections> measured;
            if(mode==7)measured=v44::measure(decoded,timing);
            if(missingStats)saveStats(hash,mode,v41::summarize(decoded,timing));
            if(measured){
                std::lock_guard<std::mutex> lock(mutex);
                gaugeKinds[hash]=measured->gaugeFlags;
                if(cache)try{
                    auto put=query(cache.get(),"INSERT OR REPLACE INTO gauge_flags_v44 VALUES(?,?)");
                    sqlite3_bind_text(put.get(),1,hash.c_str(),-1,SQLITE_TRANSIENT);
                    sqlite3_bind_int(put.get(),2,measured->gaugeFlags);sqlite3_step(put.get());
                } catch(const std::exception&) {}
            }''')
    a=s.index('                double hard;\n',s.index('            Entry result{};'));b=s.index('            } else if(auto cached=',a)
    s=s[:a]+'''                result.scores=v44::scores(*measured);
                const auto lamps=v44::chartLamps(*measured,decoded.judgeRank);
                result.hard=lamps.hard;
                if(const auto* known=clearCatalog.find(hash,mode))
                    result.hard=known->referenceHard.value_or(known->inferredHard)/100.;
                result.traits=assessPassages(decoded.notes,7,decoded.total).traits;
'''+s[b:];f.write_text(s,encoding='utf-8')
    # Keep the chart-only predictor identical in fresh files and cache misses.
    f=r/'clear_estimate.hpp';s=f.read_text();s=replace(s,'#include "clear_model.hpp"','#include "clear_model.hpp"\n#include "model44.hpp"')
    s=replace(s,'result.easy=model::predict(features,0);result.hard=model::predict(features,1);','const auto v=v44::chartLamps(v44::measure(chart,timing),chart.judgeRank);\n        result.easy=v.easy;result.hard=v.hard;')
    f.write_text(s)
    f=r/'presentation.hpp';s=f.read_text();a=s.index('        // At low difficulty');b=s.index('        view.labelColors',a)
    s=s[:a]+'        view.radii[i]=scores[i]/600.;\n'+s[b:];f.write_text(s)
    f=r/'display.hpp';s=f.read_text().replace('#include "player_rating.hpp"','#include "player_rating.hpp"\n#include "model44.hpp"')
    s=replace(s,'    if (player) drawCounter({387,567},overall,false);','    if (player) drawCounter({387,567},overall,false);\n    else drawCounter({387,482},overall>0.?overall:v44::compound(target),true);')
    f.write_text(s)
    f=r/'select_canvas.hpp';s=f.read_text()
    s=replace(s,'    void hardPoor(int cents)', '''    void gaugeMark() {
        // An amber exclamation beside the gauge traits. Draw in skin coordinates.
        const RGB ink{255,187,68};
        line({138,830},{138,836},ink,2);line({138,839},{138,840},ink,2);
    }
    void hardPoor(int cents)''');f.write_text(s)
    f=r/'selector_native.hpp';s=f.read_text();s=replace(s,'(!song && profile)?profile->overall:0.','(!song && profile)?profile->overall:(song?catalog.patternRating(key,item->keymode):0.)');s=replace(s,'if (poorExtra) canvas.hardPoor(*poorExtra);','if (poorExtra) canvas.hardPoor(*poorExtra);\n                    if(catalog.gaugeFlags(key,item->keymode))canvas.gaugeMark();');f.write_text(s)
    f=r/'tests'/'select_render.cpp';s=f.read_text();pos=s.index('    if(canvas.textures[9]<0)')
    s=s[:pos]+'''    {
        ChartCatalog catalog(std::string(assetDir)+"charts-v26.tsv");
        for(auto sample:{std::pair<const char*,const char*>{"5dc1e3e22e4fc735f010e35f2ae77480","buntan"},
                         {"22f71b0463955fcedb84eca9d09e60ca","celestial"},{"90709c02ee7092b30907df62ed3bed40","liberte"}}){
            auto v=catalog.find(sample.first);auto info=catalog.selectionStats(sample.first,7);
            if(!v||!info)return 36;
            DrawBox(0,0,1920,1080,GetColor(18,21,25),TRUE);
            drawPanel(canvas,*v,false,catalog.patternRating(sample.first,7),1.);canvas.selectionRow(0,info->easy);canvas.selectionRow(1,info->hard);
            canvas.selectionRow(2,info->average);canvas.selectionRow(3,info->maximum);
            if(auto traits=catalog.traits(sample.first,7))canvas.chartTraits(*traits);
            if(auto poor=catalog.poorExtra(sample.first,7))canvas.hardPoor(*poor);
            if(catalog.gaugeFlags(sample.first,7))canvas.gaugeMark();
            const auto p=(out/(backend+"-v44-"+sample.second+".png")).string();
            if(SaveDrawScreenToPNG(705,135,1243,1025,p.c_str())<0)return 37;
        }
    }
''' +s[pos:];f.write_text('#include "../catalog.hpp"\n'+s)
if __name__=='__main__':install(Path(sys.argv[1])/'LR2/chart_radar')
