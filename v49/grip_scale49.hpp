#pragma once
#include "grip49.hpp"
namespace chart_radar::v49 {
struct Knot { double load, score; };
inline constexpr Knot jackScale[] = {{0, 0}, {6.89421575885865, 189.75}, {10.8312540024103, 226.136}, {13.6447620893619, 265.338}, {16.6717505936001, 409.79}, {21.3187509279681, 613.78}, {28.4732379412372, 708.3452}};
inline constexpr Knot chordScale[] = {{0, 0}, {3.70005692020525, 287.3275}, {7.90770221107385, 503.389}, {11.9775627980612, 729.0655}, {17.9668955473603, 857.5275}, {22.3682314026284, 949.279}, {27.9088263135253, 1019.5404}};
inline double gripScore(const std::array<double,10>& features, const Knot (&scale)[7]) {
    const double load=.25*features[0]+.45*features[1]+.30*features[2];
    for (size_t i=1;i<std::size(scale);++i) {
        const auto &a=scale[i-1], &b=scale[i];
        if (load<=b.load) return a.score+(b.score-a.score)*(load-a.load)/(b.load-a.load);
    }
    const auto &a=scale[5], &b=scale[6];
    return b.score+(b.score-a.score)*std::log1p((load-b.load)/(b.load-a.load));
}
}
