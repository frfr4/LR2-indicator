"""Recreate the Walkure peak-unit fit and compare it to native published scores."""
import csv
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TARGETS = (0, 100, 150, 200, 700, 750, 800)


def limits(anchors):
    groups = [[float(row["load"]) for row in anchors if int(row["band"]) == band]
              for band in (0, 1)]
    return [0.] + [point for group in groups for point in
                   (.90 * min(group), statistics.median(group), 1.12 * max(group))]


def peak(load, knots):
    for i in range(1, len(knots)):
        if load <= knots[i]:
            fraction = (load - knots[i-1]) / (knots[i] - knots[i-1])
            return TARGETS[i-1] + fraction * (TARGETS[i] - TARGETS[i-1])
    return TARGETS[-1] + .7 * (load-knots[-1])


def main():
    with (ROOT / "peak-reference.tsv").open() as fp:
        refs = list(csv.DictReader(fp, delimiter="\t"))
    scores = {fields[0]: max(map(float, fields[1:9]))
              for fields in csv.reader((ROOT/"charts-v50.tsv").read_text().splitlines(),
                                       delimiter="\t")}
    training = [row for row in refs if row["fit"] == "1"]
    full = limits(training)
    folds = [limits([row for row in training if int(row["family_fold"]) != fold])
             for fold in range(5)]
    assert all(a < b for knots in [full]+folds for a, b in zip(knots, knots[1:]))
    for band, (low, high) in enumerate(((100, 200), (700, 800))):
        values, blind = [], []
        for row in refs:
            if int(row["band"]) != band:
                continue
            load = float(row["load"])
            measured = scores[row["md5"]]
            assert abs(measured - peak(load, full)) < .0051, row["md5"]
            values.append(measured)
            blind.append(peak(load, folds[int(row["family_fold"])]))
        hits = lambda a: sum(low <= x <= high for x in a)
        print(f"{low}..{high}: native {hits(values)}/{len(values)}, family-fold {hits(blind)}/{len(blind)}, "
              f"min/median/max {min(values):.2f}/{statistics.median(values):.2f}/{max(values):.2f}")
        assert hits(values) == hits(blind) == len(values)


if __name__ == "__main__":
    main()
