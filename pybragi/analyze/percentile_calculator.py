import numpy as np

def parse_infer_delta(data, tag=""):
    print(f"========== {tag} ==========")
    percentiles = np.percentile(data, [10, 30, 50, 80, 90, 95, 99])
    mean = np.mean(data)
    median = np.median(data)
    max_value = np.max(data)
    sum_value = np.sum(data)

    info = """
    ## {:}  sum: {:.3f}  median: {:.3f} max: {:.3f}
    | len | mean   | p10    | p30    | p50    | p80    | p90    | p95    | p99    |
    |-----|--------|--------|--------|--------|--------|--------|--------|--------|
    | {:.1f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.3f} |
    """.format(tag, sum_value, median, max_value, len(data), mean, \
            percentiles[0], percentiles[1], percentiles[2], percentiles[3], percentiles[4], percentiles[5], percentiles[6]
        )

    print(info)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--data", type=str, required=True)
    parser.add_argument("-t", "--tag", type=str, default="")
    args = parser.parse_args()

    data = np.array([float(x) for x in args.data.strip(',').split(',')])
    print(f"view first 10: {data[:10]}")
    parse_infer_delta(data, args.tag)
