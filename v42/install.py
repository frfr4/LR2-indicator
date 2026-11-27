"""Overlay the selection catalog on the pinned OpenLR2 v41 source tree."""
from pathlib import Path
from shutil import copyfile
import sys
src=Path(__file__).resolve().parent
root=Path(sys.argv[1])
radar=root/'LR2/chart_radar'
catalog=radar/'catalog.hpp'
s=catalog.read_text(encoding='utf8')
def replace_once(old,new):
    global s
    if s.count(old)!=1: raise RuntimeError('Unexpected v41 source: '+old)
    s=s.replace(old,new,1)
replace_once('#include "clear_estimate.hpp"','#include "clear_estimate.hpp"\n#include "clear_catalog.hpp"')
replace_once('    v40::Grades grades;', '    v40::Grades grades;\n    v42::ClearCatalog clearCatalog;')
replace_once('const std::string& cachePath={}) {','const std::string& cachePath={})\n        : clearCatalog(std::filesystem::u8path(file).parent_path()/"clear-v42.tsv") {')
replace_once('if(it!=statistics.end())return it->second;', '''if(it!=statistics.end()) {
            auto row=it->second;
            clearCatalog.apply(hash,mode,row);
            return row;
        }''')
copyfile(src/'clear_catalog.hpp',radar/'clear_catalog.hpp')
catalog.write_text(s,encoding='utf8')
