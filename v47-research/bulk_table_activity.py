"""Read the archive's published difficulty-table pages, one HTTP request at a time."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import csv,re,time,json,sys

class Table(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag=='td' and self.row is not None:self.cell=['',[]]
        if tag=='a' and self.cell is not None:self.cell[1].append(dict(attrs).get('href',''))
    def handle_data(self,s):
        if self.cell is not None:self.cell[0]+=s
    def handle_endtag(self,t):
        if t=='td' and self.cell is not None:self.row.append(self.cell);self.cell=None
        if t=='tr' and self.row:self.rows.append(self.row);self.row=None
def read(path):
    time.sleep(.27)
    with urlopen(Request(urljoin('https://lr2ir.com',path),headers={'User-Agent':'OpenLR2 chart difficulty research/1.0'}),timeout=15) as fp:
        parser=Table();parser.feed(fp.read(3<<20).decode());return parser.rows

def run(catalog,dest):
    wanted={l.split('\t')[0] for l in catalog.read_text().splitlines()}
    found={};meta=Counter();tables=[]
    try:
        for row in read('/tables'):
            if len(row)!=3:continue
            if row[0][0].strip().casefold() in ['insane','overjoy','stella','satellite','saturn','solomon','genocide','normal','insane 2','genoside'] or row[1][0].strip() in ['★','★★','st','sl','sn','✡']:
                tables+=row[0][1]
        levels=[]
        for t in sorted(set(tables)):
            for row in read(t):
                if len(row)==2:levels+=row[0][1]
        for l in sorted(set(levels)):
            try:page=read(l)
            except HTTPError as e:
                if e.code in (401,403,429):raise
                meta['level_error_'+str(e.code)]+=1;continue
            meta['level_pages']+=1
            for row in page:
                if len(row)!=4 or not row[0][1]:continue
                h=row[0][1][0].split('/charts/')[-1]
                if h not in wanted:continue
                nums=[re.search(r'(\d[\d,.]*)',r[0]) for r in row[-2:]]
                if all(nums):found[h]=(int(nums[0][1].replace(',','')),float(nums[1][1].replace(',','')))
    except Exception as e:meta['stopped_'+type(e).__name__+(str(e.code) if isinstance(e,HTTPError) else '')]=1
    with (dest/'table_play_exposure.csv').open('w') as fp:
        w=csv.writer(fp);w.writerow(['md5','archive_total_attempts','archive_percent_of_players_ever_cleared'])
        w.writerows((k,*v) for k,v in sorted(found.items()))
    m={'tables':len(set(tables)),'matched':len(found),'target':len(wanted),**meta}
    (dest/'table_coverage.json').write_text(json.dumps(m));print(m)

if __name__=='__main__':run(Path(sys.argv[1]),Path(sys.argv[2]))
