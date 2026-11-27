#pragma once
#include "mini47_params.hpp"
namespace chart_radar::v47 {
inline double mixedRehitFloor(const std::array<double,10>& motor) {
    constexpr unsigned fields[]={0,1,2,4,6,8};
    double estimate=0.;
    for (size_t j=0;j<std::size(fields);++j) {
        const double v=std::log1p(motor[fields[j]]/minifit::scale[j]);
        double left=0.;
        for(size_t k=0;k<std::size(minifit::knots[j]) && v>left;++k) {
            const double right=minifit::knots[j][k];
            double amount=(v-left)/std::max(.16,right-left);
            if (k+1<std::size(minifit::knots[j]))amount=std::min(1.,amount);
            estimate+=100.*minifit::increments[j][k]*amount;
            left=right;
        }
    }
    // Require measured upper-window load and resumption strain from the
    // embedded re-hits themselves before counting a full difficulty floor.
    const double dose=std::sqrt(motor[4]*motor[6]);
    return std::min(estimate,std::sqrt(estimate*minifit::doseScale*dose));
}
}
