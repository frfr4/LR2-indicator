#pragma once
#include "compound47_params.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iterator>
namespace chart_radar::v47::joint47 {
inline double smoothPositive(double x) {
    // Stable softplus, in radar-point units.
    return std::max(0.,x)+50.*std::log1p(std::exp(-std::abs(x)/50.));
}
inline double summary(const std::array<double,17>& scores,double upper) {
    double demand=0.;
    for(size_t interval=0;interval<std::size(cut);++interval) {
        for(size_t j=0;j<scores.size();++j) {
            double contribution=std::max(0.,scores[j]-cut[interval]);
            if(interval+1<std::size(cut))contribution=std::min(contribution,cut[interval+1]-cut[interval]);
            demand+=slope[interval][j]*contribution;
        }
    }
    // The first term increases smoothly toward the transition. The second
    // retains the more stable extrapolation on extremely difficult charts.
    return demand-smoothPositive(demand-750.)+smoothPositive(upper-750.);
}
}
