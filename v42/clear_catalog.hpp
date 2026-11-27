#pragma once
#include <algorithm>
#include <charconv>
#include <filesystem>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>

namespace chart_radar::v42 {
struct ClearRow {
    std::optional<int> referenceEasy, referenceHard;
    int inferredEasy, inferredHard;
};
inline bool parseCents(const std::string& token,int& out) {
    const auto end=token.data()+token.size();
    const auto result=std::from_chars(token.data(),end,out);
    return result.ec==std::errc{} && result.ptr==end && out>=-10000 && out<=10000;
}
inline bool parseReference(const std::string& token,std::optional<int>& out) {
    if(token==".")return true;
    int value=0;
    if(!parseCents(token,value))return false;
    out=value;return true;
}
class ClearCatalog {
    std::unordered_map<std::string,ClearRow> rows;
public:
    explicit ClearCatalog(const std::filesystem::path& file) {
        std::ifstream stream(file);
        std::string line;
        while(std::getline(stream,line)) {
            std::istringstream input(line);
            std::string hash,re,ie,rh,ih,extra;
            ClearRow row{};
            if(!(input>>hash>>re>>ie>>rh>>ih) || (input>>extra))continue;
            if(hash.size()!=32 || hash.find_first_not_of("0123456789abcdef")!=std::string::npos)continue;
            if(parseReference(re,row.referenceEasy) && parseReference(rh,row.referenceHard) &&
               parseCents(ie,row.inferredEasy) && parseCents(ih,row.inferredHard))
                rows.emplace(hash,row);
        }
    }
    const ClearRow* find(const std::string& hash,int mode) const {
        if(mode!=7)return nullptr;
        const auto it=rows.find(hash);
        return it==rows.end()?nullptr:&it->second;
    }
    template<class Stats> void apply(const std::string& hash,int mode,Stats& result) const {
        if(const auto* row=find(hash,mode)) {
            result.easy=row->referenceEasy.value_or(row->inferredEasy)/100.;
            result.hard=row->referenceHard.value_or(row->inferredHard)/100.;
        }
    }
};
}
