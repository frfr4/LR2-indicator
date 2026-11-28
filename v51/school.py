from urllib.request import urlopen
from pathlib import Path
import json,hashlib,sys,time
sys.path.insert(0,'v50')
from collect import fetch_chart
URL='https://raw.githubusercontent.com/lets-go-time-hell/Arm-Shougakkou-table/main/header.json'
def main():
    out=Path('metrics');out.mkdir(exist_ok=True);charts=Path('charts');charts.mkdir(exist_ok=True)
    source=json.load(urlopen(URL,timeout=25))['data_url']
    members=json.load(urlopen(source,timeout=45))
    excluded={r.split('\t')[0] for file in ['v51/reports.tsv','v50/controls.tsv','v50/video.tsv'] for r in Path(file).read_text().splitlines()}
    pool={r['md5'].lower():r['title'] for r in members if r.get('md5') and r['md5'].lower() not in excluded}
    keys=sorted(pool,key=lambda k:hashlib.sha256(k.encode()).digest())[:28]
    (out/'school.tsv').write_text(''.join(k+'\t'+pool[k]+'\n' for k in keys))
    for k in keys:
        fetch_chart(charts,k);time.sleep(.25)
if __name__=='__main__':main()
