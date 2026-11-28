#pragma once
#include <algorithm>
#include <array>
#include <cmath>

namespace chart_radar::v50 {
// Physical units are calibrated once. Neither the Walkure grade nor chart ID
// is an input when rating a chart. Preserve the relative geometry of all axes.
inline double peakUnits(double measured) {
    constexpr std::array<double,7> input{0.0000000000,254.1946356889,342.6602854140,548.8686385648,623.8766866617,925.2018486758,1318.6973120242};
    constexpr std::array<double,7> output{0.,100.,150.,200.,700.,750.,800.};
    for (size_t i=1;i<input.size();++i) {
        if (measured<=input[i]) {
            const double fraction=(measured-input[i-1])/(input[i]-input[i-1]);
            return output[i-1]+fraction*(output[i]-output[i-1]);
        }
    }
    return output.back()+.7*(measured-input.back());
}

inline Scores calibratePeak(Scores measured, const Scores& physical) {
    const double peak=*std::max_element(measured.begin(),measured.end());
    if (peak==0.) return measured;
    const double reference=*std::max_element(physical.begin(),physical.end());
    const double target=peakUnits(std::sqrt(peak*reference));
    for (double& value:measured) value=std::round(value*(target/peak)*100.)/100.;
    return measured;
}
}
