"""Extract independent aggregate observations for calibration, excluding HARD clears."""
import csv, gzip, hashlib, io, sys, urllib.request
from pathlib import Path
sys.path.insert(0,'v48')
from rebuild import HISTORY_URL,HISTORY_SHA

def main():
    with urllib.request.urlopen(HISTORY_URL,timeout=120) as response:
        data=response.read()
    if data.startswith(b'\x1f\x8b'):
        data=gzip.decompress(data)
    if hashlib.sha256(data).hexdigest()!=HISTORY_SHA:
        raise ValueError('unexpected historical source')
    rows=csv.DictReader(io.TextIOWrapper(io.BytesIO(data),encoding='utf-8-sig',errors='replace'))
    print(rows.fieldnames)
    fields=[k for k in rows.fieldnames if k in ('md5','players_count') or
            (('count' in k or 'rate' in k) and any(i in k for i in ('normal','easy','fullcombo','full_combo','failed','no_play','rank_','aaa','aa_')))]
    keys={r.split('\t')[0] for r in Path('v43/clear-v43.tsv').read_text().splitlines()}
    with open('observations.tsv','w',encoding='utf8',newline='') as f:
        out=csv.DictWriter(f,fields,delimiter='\t',extrasaction='ignore');out.writeheader()
        for row in rows:
            if row['md5'].lower() in keys:out.writerow(row)
if __name__=='__main__':main()
