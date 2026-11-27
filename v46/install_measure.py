from pathlib import Path
from shutil import copyfile
P=Path(__file__).resolve().parent
def repl(p,a,b):
 s=p.read_text();assert s.count(a)==1,(p,a);p.write_text(s.replace(a,b))
def install_measure(root):
 for n in ['passage46.hpp','scroll_context.hpp']:copyfile(P/n,root/n)
 f=root/'reading45.hpp'
 repl(f,'#include "v37_measure.hpp"','#include "v37_measure.hpp"\n#include "scroll_context.hpp"')
 repl(f,'struct Reading {','struct Reading {\n    v46::ScrollContext context{};')
 repl(f,'const double base=*median;','const double base=*median;\n    result.context=v46::scrollContext(current,prior,frames,base);')
 repl(f,'const std::vector<v37::Frame>& frames) {','const std::vector<v37::Frame>& frames,std::vector<double>* loads=nullptr) {')
 repl(f,'    return result;\n}', '    if(loads)*loads=std::move(bins);\n    return result;\n}')
 f=root/'sections.hpp'
 repl(f,'#include "reading45.hpp"','#include "reading45.hpp"\n#include "passage46.hpp"')
 repl(f,'v45::Reading scrollReading{};', 'v45::Reading scrollReading{};\n    v46::LocalAxes local{};')
 repl(f,'out.scrollReading=v45::measureReading(chart,frames);', 'std::vector<double> scrollLoads;\n    out.scrollReading=v45::measureReading(chart,frames,&scrollLoads);\n    out.local=v46::passages(events,scrollLoads,frames);')
if __name__=='__main__':
 import sys
 install_measure(Path(sys.argv[1])/'LR2/chart_radar')
