from pathlib import Path
import argparse, csv, gzip
import pandas as pd, numpy as np
def export(features,validation,out):
    f=np.load(features);ids=f['ids'];fold=f['fold'];fam=f['group']
    scores=pd.read_csv(validation).query("model=='v43'")
    idx={h:i for i,h in enumerate(ids)}
    with gzip.open(out/'all_matched_pairs.csv.gz','wt',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream);w.writerow(['target_md5','gauge','target_fold','anchor_md5','anchor_fold','both_played','target_only_reached','anchor_only_reached'])
        for g,name in enumerate(['easy','hard']):
            valid=set(scores[scores.gauge.eq(name)&scores.reference.notna()].md5)
            near=f['near'+str(g)];pairs=f['pairs'+str(g)]
            for i in np.flatnonzero(fold>=0):
                for j,(both,left,right) in zip(near[i],pairs[i]):
                    if ids[j] in valid and fold[j]!=fold[i] and fam[i]!=fam[j]:
                        w.writerow([ids[i],name,fold[i],ids[j],fold[j],both,left,right])
    fail=scores.loc[scores['pass'].eq(False)].sort_values(['gauge','error_cents'],ascending=[True,False])
    fail.to_csv(out/'failed_charts.csv',index=False,encoding='utf-8-sig')
if __name__=='__main__':
    a=argparse.ArgumentParser()
    for field in ('features','validation','out'):a.add_argument(field,type=Path)
    args=a.parse_args();export(args.features,args.validation,args.out)
