#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <vector>

// The published chart parameters from permitted reference families define the
// ruler. Target-family charts never enter either derivative or sample count.
extern "C" void strengths(int nusers, int nitems, const int *offsets, const int16_t *items,
                          const uint8_t *rank, const int8_t *fold, unsigned exclude,
                          const double *params, int mode, double *result, double *info, int *counts) {
    constexpr int bins = 1101;
    constexpr double start=-4.;
    std::vector<float> deriv(size_t(nitems)*bins*5), hess(deriv.size());
    for (int i=0;i<nitems;i++) {
        if (fold[i]<0 || (exclude & (1u<<fold[i]))) continue;
        const double a=params[5*i+4];
        for (int k=0;k<bins;k++) {
            const double theta=start+k*.01;
            std::array<double,6> q{1,0,0,0,0,0};
            for(int g=0;g<4;g++) q[g+1]=1./(1.+std::exp(a*(params[5*i+g]-theta)));
            for(int g=0;g<5;g++) {
                const int j=(i*bins+k)*5+g;
                deriv[j]=a*(1.-q[g]-q[g+1]);
                hess[j]=a*a*(q[g]*(1.-q[g])+q[g+1]*(1.-q[g+1]));
            }
        }
    }
    #pragma omp parallel for num_threads(2) schedule(dynamic,48)
    for (int person=0;person<nusers;person++) {
        std::vector<int> rows;
        for(int j=offsets[person];j<offsets[person+1];j++){
            int i=items[j]; if(fold[i]>=0 && !(exclude&(1u<<fold[i])))rows.push_back(j);
        }
        const double prior=mode==1 ? .02 : .70;
        double th=0, information=prior;
        for(int iter=0;iter<12;iter++){
            const auto k=std::clamp(int(std::lround((th-start)*100.)),0,bins-1);
            double s=-prior*th;information=prior;
            for(auto j:rows){
                const int index=(int(items[j])*bins+k)*5+int(rank[j])-1;
                s+=deriv[index];information+=hess[index];
            }
            double step=std::clamp(s/information,-1.1,1.1);
            th=std::clamp(th+step,start,7.);
            if(std::abs(step)<.006)break;
        }
        result[person]=th;info[person]=information;counts[person]=rows.size();
    }
}
