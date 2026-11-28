#include "catalog.hpp"
#include <fstream>
#include <iostream>
#include <set>
#include <stdexcept>

using namespace chart_radar;

static void require(bool condition, const std::string& detail) {
    if (!condition) throw std::runtime_error(detail);
}

int main(int argc, char** argv) {
    if (argc != 2 && argc != 3) return 1;
    try {
        const auto root = std::filesystem::path(argv[1]);
        ChartCatalog catalog((root/"no-base-table").string(), argc==3 ? argv[2] : "");
        std::ifstream charts(root/"charts-v47.tsv"), clears(root/"clear-v43.tsv"), select(root/"selection-v47.tsv");
        std::string line, clearLine, selectLine;
        std::set<std::string> seen;
        unsigned officialEasy=0, officialHard=0, negativeEasy=0, hiddenEasy=0;
        while (std::getline(charts, line)) {
            require(bool(std::getline(clears,clearLine)) && bool(std::getline(select,selectLine)), "missing row");
            std::istringstream chart(line), clear(clearLine), choice(selectLine);
            std::string id, cId, sId, refEasy, refHard;
            int infEasy, infHard, flags;
            double avg, maximum, fallbackEasy, fallbackHard, rating;
            require(bool(chart>>id) && bool(clear>>cId>>refEasy>>infEasy>>refHard>>infHard) &&
                    bool(choice>>sId>>avg>>maximum>>fallbackEasy>>fallbackHard>>flags>>rating), "invalid selection row");
            require(id==sId && id==cId && seen.insert(id).second, "misordered or duplicate hash "+id);
            const auto scores=catalog.find(id,7);
            const auto stats=catalog.selectionStats(id,7);
            require(scores.has_value() && stats.has_value(), "game failed to load "+id);
            for (auto axis:detailOrder) {
                double expected;
                require(bool(chart>>expected) && (*scores)[axis]==expected, "axis mismatch "+id);
            }
            require(catalog.gaugeFlags(id,7)==flags && stats->average==avg && stats->maximum==maximum &&
                    catalog.patternRating(id,7)==rating, "pattern/gauge/summary mismatch "+id);
            officialHard+=(refHard!=".");
            officialEasy+=(refEasy!=".");
            negativeEasy+=(refEasy!="." && std::stoi(refEasy)<0);
            const double hard=(refHard=="." ? infHard : std::stoi(refHard))/100.;
            require(stats->hard && *stats->hard==hard, "HARD mismatch "+id);
            if ((flags&8) && refEasy==".") {
                ++hiddenEasy;
                require(!stats->easy, "impossible EASY visible "+id);
            } else {
                const double easy=(refEasy=="." ? infEasy : std::stoi(refEasy))/100.;
                require(stats->easy && *stats->easy==easy, "EASY mismatch "+id);
            }
        }
        require(!std::getline(clears,clearLine) && !std::getline(select,selectLine), "extra selection rows");
        require(seen.size()==6226 && officialEasy==1249 && officialHard==1236 && negativeEasy==9 && hiddenEasy==1,
                "catalog coverage changed");
        std::cout<<"{\"rows\":"<<seen.size()<<",\"axes\":"<<8*seen.size()
                 <<",\"official_easy\":"<<officialEasy<<",\"official_hard\":"<<officialHard
                 <<",\"negative_official_easy\":"<<negativeEasy<<",\"hidden_impossible_easy\":"<<hiddenEasy<<"}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr<<e.what()<<"\n";
        return 2;
    }
}
