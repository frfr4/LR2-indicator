"""Build the validation sample of published Walkure EASY/HARD anchor charts."""
from pathlib import Path
from collect import fetch_chart
import time
def main():
    folder=Path('anchors');folder.mkdir(exist_ok=True)
    for l in Path('v50/anchors.tsv').read_text().splitlines():
        h,e,hard,tier=l.split('\t')
        keep=any(v!='.' and (3<=float(v)<=5 or 24<=float(v)<=25) for v in (e,hard))
        if not keep:continue
        fetch_chart(folder,h)
        time.sleep(.35)
if __name__=='__main__':main()
