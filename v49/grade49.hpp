#pragma once
#include <fstream>
#include <string>
#include <unordered_map>

namespace chart_radar {
using RegisteredGrades = std::unordered_map<std::string,int>;
inline RegisteredGrades readGrades(const std::string& path) {
    RegisteredGrades grades;
    std::ifstream file(path);
    std::string hash;
    int label;
    while (file >> hash >> label)
        if (label >= 0 && label < 60) grades.emplace(hash, label);
    return grades;
}
}
