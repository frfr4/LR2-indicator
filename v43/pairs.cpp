// Four bitmaps per chart: observed, EASY+, NORMAL+, HARD+. Only the
// intersection of two observed populations contributes discordant lamps.
#include <cstdint>
#include <cstdio>
#include <vector>
#include <fstream>
#include <stdexcept>
int main(int argc,char**argv) {
    if(argc!=5)return 1;
    std::ifstream pack(argv[1],std::ios::binary),neighbors(argv[2],std::ios::binary);
    std::ofstream out(argv[3],std::ios::binary);
    int shape[3];neighbors.read(reinterpret_cast<char*>(shape),sizeof(shape));
    const int charts=shape[0],count=shape[1],words=shape[2], gauge=std::stoi(argv[4]);
    std::vector<uint64_t> bits(size_t(charts)*4*words);
    if(!pack.read(reinterpret_cast<char*>(bits.data()),bits.size()*8))return 2;
    for(int i=0;i<charts;i++)for(int k=0;k<count;k++){
        int j; if(!neighbors.read(reinterpret_cast<char*>(&j),4))return 3;
        const auto* a=&bits[size_t(i)*4*words];const auto* b=&bits[size_t(j)*4*words];
        int stats[3]={};
        for(int x=0;x<words;x++){
            const auto common=a[x]&b[x],won=a[gauge*words+x],other=b[gauge*words+x];
            stats[0]+=__builtin_popcountll(common);
            stats[1]+=__builtin_popcountll(common&won&~other);
            stats[2]+=__builtin_popcountll(common&other&~won);
        }
        out.write(reinterpret_cast<char*>(stats),sizeof(stats));
    }
    return !out;
}
