#include "catalog.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
using namespace chart_radar;

namespace {
void check(bool good,const char* text) {if(!good)throw std::runtime_error(text);}
void command(sqlite3* db,const char* sql) {check(sqlite3_exec(db,sql,nullptr,nullptr,nullptr)==SQLITE_OK,sqlite3_errmsg(db));}
struct Frame { double t; unsigned keys; };
double stagger(const std::vector<unsigned>& masks,const std::vector<double>& gaps) {
    double time=0.;std::vector<Frame> rows;
    for(size_t i=0;i<240;++i){
        rows.push_back({time,masks[i%masks.size()]});time+=gaps[i%gaps.size()];
    }
    return v47::staggerActions(rows)[0];
}
std::array<double,10> embedded(const std::vector<unsigned>& keys,double dt,bool mirror=false){
    std::vector<Frame> frames;
    for(size_t i=0;i<192;++i){
        unsigned mask=keys[i%keys.size()];
        if(mirror){
            unsigned reflected=0;
            for(int k=0;k<7;++k)if(mask&(1u<<k))reflected|=1u<<(6-k);
            mask=reflected;
        }
        frames.push_back({i*dt,mask});
    }
    return v47::miniJacks(frames);
}
void writeChart(const std::filesystem::path& path){
    std::ofstream f(path);
    f<<"#PLAYER 1\n#TITLE gauge edge\n#BPM 150\n#RANK 2\n#TOTAL 6.66\n";
    for(int bar=10;bar<21;++bar){
        f<<"#0"<<bar<<"11:01010101\n#0"<<bar<<"12:00010001\n";
    }
}
}
int main(int argc,char** argv) try {
    if(argc!=2)return 1;
    const std::filesystem::path dir=argv[1];std::filesystem::create_directories(dir);
    const auto chart=dir/"special.bms",dbFile=dir/"v47-check.db",catalogPath=dir/"charts-v26.tsv";
    const std::string hidden(32,'a'),overridden(32,'b'),regular(32,'c'),cached(32,'d');
    writeChart(chart);
    {
        std::ofstream f(dir/"clear-v43.tsv");
        f<<hidden<<" . 1357 . 1600\n"<<overridden<<" -102 1357 . 1600\n";
        std::ofstream summaries(dir/"selection-v47.tsv");
        summaries<<overridden<<" 8 12 -1 15 8 115\n"<<regular<<" 8 12 -1.00 15 0 115\n";
    }
    {
        sqlite3* raw=nullptr;
        check(sqlite3_open(dbFile.string().c_str(),&raw)==SQLITE_OK,"open cache");
        Database db(raw,sqlite3_close);
        command(raw,"CREATE TABLE IF NOT EXISTS radar_v46_chart(hash TEXT,mode INTEGER,a INTEGER,b INTEGER,c INTEGER,d INTEGER,e INTEGER,f INTEGER,g INTEGER,h INTEGER,end_spike INTEGER,shortfall INTEGER,hard REAL,PRIMARY KEY(hash,mode))");
        command(raw,"CREATE TABLE IF NOT EXISTS selection_stats_v44(hash TEXT,mode INTEGER,average REAL,maximum REAL,easy REAL,hard REAL,PRIMARY KEY(hash,mode))");
        command(raw,"INSERT OR REPLACE INTO radar_v46_chart VALUES('dddddddddddddddddddddddddddddddd',7,1,2,3,4,5,6,7,8,0,4,5.1),('dddddddddddddddddddddddddddddddd',5,1,2,3,4,5,0,7,8,0,4,NULL)");
        command(raw,"INSERT OR REPLACE INTO selection_stats_v44 VALUES('dddddddddddddddddddddddddddddddd',7,777,778,9,10),('dddddddddddddddddddddddddddddddd',5,77,78,NULL,NULL)");
    }
    {
        ChartCatalog cat(catalogPath.string(),dbFile.string());
        check(!cat.find(cached,7) && !cat.selectionStats(cached,7),"stale seven-key cache");
        check(cat.find(cached,5).has_value() && cat.selectionStats(cached,5)->average==77.,"non-seven-key cache migration");
        check(cat.selectionStats(overridden,7)->easy.value()==-1.02,"observed EASY overrides impossible marker");
        check(cat.selectionStats(regular,7)->easy.value()==-1.00,"legitimate value equal to handoff sentinel survives");
        const auto result=cat.resolve(hidden,chart.string(),7,true,true);check(result.has_value(),"local resolve");
        const auto stats=cat.selectionStats(hidden,7);
        check(stats.has_value() && !stats->easy && stats->hard.has_value(),"inferred EASY cannot override an impossible gauge");
        check(cat.gaugeFlags(hidden,7)&8,"raw gauge rule propagated");
        RadarTempo timing;auto parsed=decodeChart(chart,7,0,&timing);
        const auto local=v44::measure(parsed,timing);
        check(local.gaugePath[gauge47::EasyPerfectEnd]>27.19 && local.gaugePath[gauge47::EasyPerfectEnd]<27.21,"fractional TOTAL truncation");
        check(local.gaugeFlags==cat.gaugeFlags(hidden,7),"identical local and cached flags");
        check(cat.hardEstimate(hidden,7)==v44::chartLamps(local,parsed.judgeRank).hard && stats->hard.value()==16.,
              "chart-only HARD and public lamp estimate have distinct accessors");
        check(v44::scores(local)==*result && v44::chartLamps(local,parsed.judgeRank).easy==-1.,"native chart and cache agree");
        check(cat.traits(hidden,7)->recoveryShortfall==assessPassages(parsed.notes,7,parsed.total).traits.recoveryShortfall,"LOW REC units");
    }
    {
        ChartCatalog reopened(catalogPath.string(),dbFile.string());
        check(reopened.find(hidden,7).has_value() && !reopened.selectionStats(hidden,7)->easy,"unreachable EASY persists on reopen");
        const auto db=readOnly(dbFile.string());
        auto row=query(db.get(),"SELECT easy,hard FROM selection_stats_v47 WHERE hash='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' AND mode=7");
        check(sqlite3_step(row.get())==SQLITE_ROW && sqlite3_column_type(row.get(),0)==SQLITE_NULL
              && sqlite3_column_type(row.get(),1)!=SQLITE_NULL,"SQLite NULL EASY and populated HARD");
    }
    check(stagger({1,2,4,8},{.064})==0.,"uniform 64 ms stream");
    check(stagger({1,2,4,8},{.025})>0. && stagger({1,2,4,8},{.038,.138})>0.,"tight roll and staggered timing");
    check(stagger({1},{.03})==0.,"single-key jack does not become a delay");
    const std::vector<unsigned> mixed{9,3,5,16,32,64};
    const auto rapid=embedded(mixed,.068),mirror=embedded(mixed,.068,true),slow=embedded(mixed,.118);
    check(rapid[1]>slow[1] && slow[1]>0.,"mixed 3-hit reattack and speed");
    check(embedded({1},.068)[7]==0. && embedded({3},.068)[7]==0.,"pure jack/chord excluded from embedded reattack");
    for(size_t j=0;j<rapid.size();++j)check(std::abs(rapid[j]-mirror[j])<1.e-8,"mirrored mixed reattack");
    std::cout<<"v47 chart and cache paths, public lamps, gauge rules and stagger controls passed\n";
    return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
