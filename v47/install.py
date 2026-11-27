"""Install the v47 radar on top of the v46 OpenLR2 source tree."""
import argparse
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent


def edit(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"v46 source mismatch near {old[:90]!r}")
    return source.replace(old, new, 1)


def section(source):
    source = edit(source, '#include "passage46.hpp"', '#include "passage46.hpp"\n#include "mechanics47.hpp"\n#include "mini47.hpp"\n#include "scratch47.hpp"\n#include "delay47.hpp"\n#include "gauge47.hpp"')
    source = edit(source, '    v46::LocalAxes local{};', '''    v46::LocalAxes local{};
    v47::HumanFeatures human{};
    std::array<double,10> mini{};
    v47::Scratch47 scratch{};
    std::array<double,10> stagger{};
    gauge47::Result gaugePath{};''')
    source = edit(source, '    out.local=v46::passages(events,scrollLoads,frames);', '''    out.local=v46::passages(events,scrollLoads,frames);
    out.human=v47::humanMechanics(frames,scrollLoads);
    out.mini=v47::miniJacks(frames);
    out.scratch=v47::scratchActions(chart.notes,frames);
    out.stagger=v47::staggerActions(frames);
    out.gaugePath=gauge47::measure(chart,timing);''')
    return edit(source, '    if(out.total>2.5*out.normalTotal)out.gaugeFlags|=4;', '''    if(out.total>2.5*out.normalTotal)out.gaugeFlags|=4;
    out.gaugeFlags|=(static_cast<int>(out.gaugePath[gauge47::GaugeFlags])&31)<<3;''')


def model(source):
    source = edit(source, '#include "scoring46.hpp"', '#include "scoring46.hpp"\n#include "axis47.hpp"\n#include "clear47.hpp"')
    start = source.index('inline Scores scores(')
    end = source.index('using ModelInput', start)
    source = source[:start] + '''inline Scores scores(const Sections& x) {
    return v47::axisScores(x.human,x,x.scratch,x.stagger);
}
inline double compound(const Scores& scores) {
    return v47::physicalRating(scores);
}
''' + source[end:]
    start = source.index('    const auto x=input(m,rank);')
    end = source.index('\n}',start)
    return source[:start] + '''    const auto lamps=v47::chartLamps47(m,rank);
    return {(m.gaugeFlags&8)?-1.:lamps[0],lamps[1]};''' + source[end:]


def estimate(source):
    source = edit(source, 'inline SelectionStats summarize(const DecodedChart& chart,const RadarTempo& timing) {',
                  'inline SelectionStats summarize(const DecodedChart& chart,const RadarTempo& timing,const v44::Sections* measured=nullptr) {')
    return edit(source, '''        const auto v=v44::chartLamps(v44::measure(chart,timing),chart.judgeRank);
        result.easy=v.easy;result.hard=v.hard;''', '''        std::optional<v44::Sections> owned;
        if(!measured){owned.emplace(v44::measure(chart,timing));measured=&*owned;}
        const auto v=v44::chartLamps(*measured,chart.judgeRank);
        if(!(measured->gaugeFlags&8))result.easy=v.easy;
        result.hard=v.hard;''')


def catalog(source):
    for old,new in [('radar_v46_chart','radar_v47_chart'),('selection_stats_v44','selection_stats_v47'),('gauge_flags_v44','gauge_flags_v47'),
                    ('charts-v46.tsv','charts-v47.tsv'),('selection-v46.tsv','selection-v47.tsv')]:
        source=source.replace(old,new)
    source=edit(source,'            row.easy=easy;row.hard=hard;', '''            if(flags&8)row.easy.reset();else row.easy=easy;
            row.hard=hard;''')
    source=edit(source, '            auto q=query(ptr,"SELECT hash,mode,average,maximum,easy,hard FROM selection_stats_v47");', '''            auto old=query(ptr,"SELECT 1 FROM sqlite_master WHERE type='table' AND name='selection_stats_v44'");
            if(sqlite3_step(old.get())==SQLITE_ROW)
                sqlite3_exec(ptr,"INSERT OR IGNORE INTO selection_stats_v47 SELECT * FROM selection_stats_v44 WHERE mode<>7",nullptr,nullptr,nullptr);
            auto q=query(ptr,"SELECT hash,mode,average,maximum,easy,hard FROM selection_stats_v47");''')
    source=edit(source, '        auto recentModes=query', '''        auto lastModes=query(ptr,"SELECT 1 FROM sqlite_master WHERE type='table' AND name='radar_v46_chart'");
        if(sqlite3_step(lastModes.get())==SQLITE_ROW)readCache(ptr,"SELECT * FROM radar_v46_chart WHERE mode<>7",entries);
        auto recentModes=query''')
    source=edit(source,'            clearCatalog.apply(hash,mode,row);', '''            clearCatalog.apply(hash,mode,row);
            const auto flags=gaugeKinds.find(hash);
            if(mode==7 && flags!=gaugeKinds.end() && (flags->second&8)){
                const auto* known=clearCatalog.find(hash,mode);
                if(!known || !known->referenceEasy)row.easy.reset();
            }''')
    source=edit(source,'            if(missingStats)saveStats(hash,mode,v41::summarize(decoded,timing));\n','')
    source=edit(source,'            const int extra=extraPoorCents','''            if(missingStats)saveStats(hash,mode,v41::summarize(decoded,timing,measured?&*measured:nullptr));
            const int extra=extraPoorCents''')
    source=edit(source,'''                if(const auto* known=clearCatalog.find(hash,mode))
                    result.hard=known->referenceHard.value_or(known->inferredHard)/100.;
''','')
    source=edit(source,'                result.traits=assessPassages(decoded.notes,7,decoded.total).traits;', '''                result.traits=assessPassages(decoded.notes,7,decoded.total).traits;
                result.traits.endSpike|=(measured->gaugePath[gauge47::EndingSpike]!=0.);''')
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo',type=Path)
    options=parser.parse_args()
    root=options.repo
    radar=root/'LR2'/'chart_radar'
    files={'sections.hpp':section, 'model44.hpp':model, 'clear_estimate.hpp':estimate, 'catalog.hpp':catalog}
    already=(radar/'axis47.hpp').exists() and 'axisScores(x.human,x,x.scratch,x.stagger)' in (radar/'model44.hpp').read_text()
    if not already:
        pending={radar/name:transform((radar/name).read_text(encoding='utf-8')) for name,transform in files.items()}
        for path,data in pending.items():
            path.write_text(data,encoding='utf-8')
    for h in (HERE/'headers').glob('*.hpp'):
        shutil.copyfile(h,radar/h.name)
    tests=radar/'tests'
    tests.mkdir(exist_ok=True)
    for path in (HERE/'tests').glob('*.cpp'):
        shutil.copyfile(path,tests/path.name)
    cmake=root/'CMakeLists.txt'
    if cmake.exists() and 'add_executable(OpenLR2V47Check ' not in cmake.read_text(encoding='utf-8'):
        with cmake.open('a',encoding='utf-8') as f:
            f.write('''
add_executable(OpenLR2V47Check EXCLUDE_FROM_ALL LR2/chart_radar/tests/v47_runtime_check.cpp)
target_compile_features(OpenLR2V47Check PRIVATE cxx_std_17)
target_compile_definitions(OpenLR2V47Check PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
target_include_directories(OpenLR2V47Check PRIVATE LR2/chart_radar)
target_link_libraries(OpenLR2V47Check PRIVATE SQLite)
''')

if __name__=='__main__':
    main()
