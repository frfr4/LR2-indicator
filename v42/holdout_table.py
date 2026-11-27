"""Make a native prediction-only catalog from the family holdout (no reference column)."""
from decimal import Decimal
import csv,sys
from pathlib import Path
def make_table(source,dest):
    values={}
    with source.open(encoding='utf8',newline='') as f:
        for row in csv.DictReader(f):
            if row['model']=='v42':
                values.setdefault(row['md5'],{})[row['gauge']]=int(Decimal(row['display'])*100)
    with dest.open('w',encoding='ascii',newline='\n') as f:
        for h,row in sorted(values.items()):
            f.write(f"{h}\t.\t{row['easy']}\t.\t{row['hard']}\n")
    assert len(values)==1252
if __name__=='__main__':make_table(Path(sys.argv[1]),Path(sys.argv[2]))
