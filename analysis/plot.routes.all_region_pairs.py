#!/usr/bin/env python3

import argparse
import csv
import io
import logging
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Any, Optional

from common import DirType, RouteMetric, Statistic, calculate_route_metric, init_logging, plot_cdf_array, weighted_median

# Global variable to hold the labels for the plots with multiple lines
plot_labels = None


def load_weighted_hops(file_path: str) -> pd.DataFrame:
    """Load the file that contains a list of weights and hops.

        File format:
        4 hop1|hop2|hop3
        1 hop1|hop2
        ...
    """
    l_weight: list[float] = []
    l_hops: list[str] = []

    with open(file_path, 'r') as file:
        reader = csv.DictReader(file, delimiter='\t')
        for row in reader:
            weight = float(row['count'])
            hops: str = row['route']
            l_weight.append(weight)
            l_hops.append(hops)

    # Create a DataFrame
    return pd.DataFrame.from_dict({'weight': l_weight, 'hops': l_hops})

def get_hops_and_weights(file_path: str) -> tuple[list[str], list[float]]:
    data = load_weighted_hops(file_path)
    hops: list[str] = data['hops'].to_list()
    weights: list[float] = data['weight'].to_list()
    return hops, weights

def extract_cloud_regions_from_filename(filename) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    Extract the source and destination (cloud, region) pairs from the given filename.
    Assumes the format: 'routes.[src].[dst].by_iso.distribution'
    """
    regex = re.compile(r'^routes\.([a-z0-9-]+)\.([a-z0-9-]+)\.([a-z0-9-]+)\.([a-z0-9-]+)\.by_(?:\w+)\.distribution$')
    m = regex.match(filename)
    assert m is not None, 'Invalid filename: {}'.format(filename)
    src_cloud = m.group(1)
    src_region = m.group(2)
    dst_cloud = m.group(3)
    dst_region = m.group(4)
    return (src_cloud, src_region), (dst_cloud, dst_region)

def plot_single_pair_pdf(values, weights, src_region: str, dst_region: str, metric: str, data_source: str):
    # Normalize the weights to ensure they sum up to 1
    weights = np.array(weights) / np.sum(weights)

    plt.figure()
    plt.hist(values, bins=len(values), weights=weights, density=True, edgecolor='black')
    plt.xlabel('Values')
    plt.ylabel('Probability')
    plt.title(f'PDF of average {metric} between regions {src_region} and {dst_region}')

    filename = f'{metric}.pdf.{data_source}.{src_region}.{dst_region}.png'
    logging.info(f'Saving heatmap to {filename} ...')
    plt.savefig(filename, bbox_inches='tight')

def plot_heatmap(src_regions: list[str], dst_regions: list[str], metric_value_by_region: dict[tuple[str, str], float],
                 metric: RouteMetric, data_source: str):
    # Create a mapping of regions to indices
    src_region_to_index = {region: index for index, region in enumerate(src_regions)}
    dst_region_to_index = {region: index for index, region in enumerate(dst_regions)}

    # Initialize a matrix for the data
    matrix = np.zeros((len(src_regions), len(dst_regions)))

    # Populate the matrix
    for (src_region, dst_region), value in metric_value_by_region.items():
        i, j = src_region_to_index[src_region], dst_region_to_index[dst_region]
        matrix[i][j] = value

    # Plotting the heatmap
    plt.figure(figsize=(10, 8))
    plt.imshow(matrix, cmap='coolwarm', interpolation='nearest')
    plt.colorbar()

    # Setting labels
    plt.xticks(ticks=np.arange(len(dst_regions)), labels=dst_regions, rotation=90)
    plt.yticks(ticks=np.arange(len(src_regions)), labels=src_regions)

    plt.title(f'Average {metric} between regions {data_source}')
    filename = f'{metric}.heatmap.{data_source}.png'
    logging.info(f'Saving heatmap to {filename} ...')
    plt.savefig(filename, bbox_inches='tight')

def get_values_and_weights_by_region_pair_from_raw_files(dirpath: str, metric: RouteMetric,
                                        src_cloud: Optional[str], src_region: Optional[str],
                                        dst_cloud: Optional[str], dst_region: Optional[str]) -> \
                                            dict[tuple[str, str], tuple[list[Any], list[float]]]:
    # Dictionary to hold the source-destination pairs and the aggregated value
    values_and_weights_by_region_pair = {}

    # Corrected processing of each file
    for file in os.listdir(dirpath):
        file_path = os.path.join(dirpath, file)
        src, dst = extract_cloud_regions_from_filename(file)

        if (src_cloud and src_cloud != src[0]) or (src_region and src_region != src[1]) or \
              (dst_cloud and dst_cloud != dst[0]) or (dst_region and dst_region != dst[1]):
            continue

        logging.info('Processing file: %s', file_path)

        # Calculate the weighted hop count for the file
        hops, weights = get_hops_and_weights(file_path)
        values = list(map(lambda x: calculate_route_metric(x, metric), hops))

        src = ':'.join(src)
        dst = ':'.join(dst)
        values_and_weights_by_region_pair[(src, dst)] = (values, weights)
    return values_and_weights_by_region_pair

def get_values_and_weights_by_region_pair_from_tsv(routes_distribution_tsv: io.TextIOWrapper, metric: RouteMetric,
                                                   src_cloud: Optional[str], src_region: Optional[str],
                                                   dst_cloud: Optional[str], dst_region: Optional[str]) -> \
                                                    dict[tuple[str, str], tuple[list[Any], list[float]]]:
    # Dictionary to hold the source-destination pairs and the aggregated value
    values_and_weights_by_region_pair = {}
    reader = csv.DictReader(routes_distribution_tsv, delimiter='\t')
    assert reader.fieldnames and metric in reader.fieldnames, f'Field {metric} not found in TSV file'
    for column in ['src_cloud', 'src_region', 'dst_cloud', 'dst_region']:
        assert reader.fieldnames and column in reader.fieldnames, f'Field {column} not found in TSV file'

    def _parse_value(value: str, metric: RouteMetric) -> Any:
        if metric == RouteMetric.HopCount:
            return int(value)
        elif metric == RouteMetric.DistanceKM:
            return float(value)
        else:
            return value

    for row in reader:
        src = (row["src_cloud"], row["src_region"])
        dst = (row["dst_cloud"], row["dst_region"])
        if (src_cloud and src_cloud != src[0]) or (src_region and src_region != src[1]) or \
                (dst_cloud and dst_cloud != dst[0]) or (dst_region and dst_region != dst[1]):
            continue
        src = ':'.join(src)
        dst = ':'.join(dst)
        key = (src, dst)
        if key not in values_and_weights_by_region_pair:
            values_and_weights_by_region_pair[key] = ([], [])
        values_and_weights_by_region_pair[key][0].append(_parse_value(row[metric], metric))
        # Try to read weight from file. If not found, default to 1.
        if 'count' in row:
            weight = float(row['count'])
        elif 'weight' in row:
            weight = float(row['weight'])
        else:
            weight = 1
        values_and_weights_by_region_pair[key][1].append(weight)
    return values_and_weights_by_region_pair

def get_weighted_average_by_region_pair(
        values_and_weights_by_region_pair: dict[tuple[str, str], tuple[list[Any], list[float]]],
        ignore_zeros: bool = False):
    weighted_average_by_region_pair = {}
    for region_pair, (values, weights) in values_and_weights_by_region_pair.items():
        values = np.array(values)
        weights = np.array(weights)
        if ignore_zeros:
            values = values[values != 0.]
            weights = weights[values != 0.]
        weighted_average_by_region_pair[region_pair] = np.average(values, weights=weights)
    return weighted_average_by_region_pair

def aggregate_values_by_region_pair(
        values_and_weights_by_region_pair: dict[tuple[str, str], tuple[list[Any], list[float]]],
        statistic: Statistic):
    aggregate_value_by_region_pair = {}
    for region_pair, (values, weights) in values_and_weights_by_region_pair.items():
        if statistic == Statistic.MEAN:
            aggregate_value_by_region_pair[region_pair] = np.average(values, weights=weights)
        elif statistic == Statistic.MEDIAN:
            aggregate_value_by_region_pair[region_pair] = weighted_median(values, weights=weights)
        elif statistic == Statistic.MIN:
            aggregate_value_by_region_pair[region_pair] = np.min(values)
        elif statistic == Statistic.MAX:
            aggregate_value_by_region_pair[region_pair] = np.max(values)
        else:
            raise ValueError(f'Unsupported statistic {statistic}')
    return aggregate_value_by_region_pair

def plot_cdf(value_by_region_pair: dict[tuple[str, str], float], metric: RouteMetric,
             aggregate_by: Statistic, label: str):
    values = list(value_by_region_pair.values())
    plot_cdf_array(values, f'{label} - {aggregate_by} {metric}', include_count=True)
    plt.xlabel('Values')
    plt.ylabel('CDF')

    # Add the label to temporary global variable. This is used to annotate the filename and title.
    global plot_labels
    if not plot_labels:
        plot_labels = label
    else:
        plot_labels = f'{plot_labels}+{label}'

def save_last_plot(metric: RouteMetric, aggregate_by: Statistic, label_cloud_region: str):
    global plot_labels
    # plt.title(f'CDF of {aggregate_by} {metric} per region-pair ({plot_labels})')
    plt.title(f'CDF of {aggregate_by} {metric} per region-pair')
    plt.legend()
    filename = f'{metric}.{aggregate_by}.cdf.{label_cloud_region}.{plot_labels}.png'
    logging.info(f'Saving heatmap to {filename} ...')
    plt.savefig(filename, bbox_inches='tight')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrics', required=True, nargs='+', type=RouteMetric, choices=list(RouteMetric),
                        help='The metrics to plot')
    parser.add_argument('--dirpaths', type=DirType, nargs='+', help='The directory that contains the routes files')
    parser.add_argument('--routes-distribution-tsvs', type=argparse.FileType('r'), nargs='+',
                        help='The TSV file that contains the routes by region pair')
    parser.add_argument('--plot-heatmap', action='store_true',
                        help='Plot the heatmap of the metric across all region pairs')
    parser.add_argument('--plot-cdf', action='store_true',
                        help='Plot the CDF of the metric across all region pairs')
    parser.add_argument('--aggregate-each-region-pair-by', type=Statistic, choices=list(Statistic),
                        help='The aggregation function to use for each region pair\'s metric values')
    parser.add_argument('--plot-individual-pdfs', action='store_true',
                        help='Plot the PDFs of the metric, one graph for each region pair')
    parser.add_argument('--src-cloud', required=False, help='The source cloud to filter on')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud to filter on')
    parser.add_argument('--src-region', required=False, help='The source region to filter on')
    parser.add_argument('--dst-region', required=False, help='The destination region to filter on')
    args = parser.parse_args()

    if not (args.plot_heatmap or args.plot_individual_pdfs or args.plot_cdf):
        parser.error('At least one of --plot-heatmap, --plot-individual-pdfs, or --plot-cdf must be specified')

    if args.dirpaths is not None != args.routes_distribution_tsvs is not None:
        parser.error('Either --dirpaths or --routes-distribution-tsvs must be specified')

    if args.src_region and not args.src_cloud:
        parser.error('--src-cloud must be specified with --src-region')

    if args.dst_region and not args.dst_cloud:
        parser.error('--dst-cloud must be specified with --dst-region')

    if args.plot_cdf:
        if not args.aggregate_each_region_pair_by:
            parser.error('--aggregate-each-region-pair-by must be specified with --plot-cdf')

    if args.src_region and not args.src_cloud:
        parser.error('--src-cloud must be specified with --src-region')
    if args.dst_region and not args.dst_cloud:
        parser.error('--dst-cloud must be specified with --dst-region')

    return args

def get_label_from_path(path: str) -> str:
    LSTRIP_PREFIXES = [
        'routes.all.',
        'routes.aws.',
        'routes.gcloud.',
    ]
    RSTRIP_SUFFIXES = [
        '.by_geo.distribution.tsv',
        '.by_geo.distribution',
    ]
    label = os.path.basename(path)
    for prefix in LSTRIP_PREFIXES:
        label = label.lstrip(prefix)
    for suffix in RSTRIP_SUFFIXES:
        label = label.rstrip(suffix)
    return label

def get_label_from_cloud_region_pair(
        src_cloud: Optional[str] = None, src_region: Optional[str] = None,
        dst_cloud: Optional[str] = None, dst_region: Optional[str] = None) -> str:
    def _get_label(cloud: Optional[str], region: Optional[str]) -> str:
        if cloud and region:
            return f'{cloud}.{region}'
        elif cloud:
            return f'{cloud}.all'
        else:
            return 'all_clouds'
    src_label = _get_label(src_cloud, src_region)
    dst_label = _get_label(dst_cloud, dst_region)
    return f'{src_label}.{dst_label}'

def run_action(args, metric, values_and_weights_by_region_pair, path):
    label = get_label_from_path(path)

    if args.plot_individual_pdfs:
        for (src, dst), (values, weights) in values_and_weights_by_region_pair.items():
            plot_single_pair_pdf(values, weights, src, dst, metric, label)

    if args.plot_heatmap:
        ignore_zeros = metric in (RouteMetric.HopCount, RouteMetric.DistanceKM)
        weighted_average_by_region_pair = get_weighted_average_by_region_pair(
                values_and_weights_by_region_pair, ignore_zeros)
        region_pairs = weighted_average_by_region_pair.keys()
        src_regions = sorted(set(t[0] for t in region_pairs))
        dst_regions = sorted(set(t[1] for t in region_pairs))
        plot_heatmap(src_regions, dst_regions, weighted_average_by_region_pair, metric, label)

    if args.plot_cdf:
        value_by_region_pair = aggregate_values_by_region_pair(
                values_and_weights_by_region_pair, args.aggregate_each_region_pair_by)
        plot_cdf(value_by_region_pair, metric, args.aggregate_each_region_pair_by, label)

def main():
    init_logging(level=logging.INFO)
    args = parse_args()

    for metric in args.metrics:
        logging.info('Processing metric %s ...', metric)
        if args.dirpaths:
            for dirpath in args.dirpaths:
                values_and_weights_by_region_pair = get_values_and_weights_by_region_pair_from_raw_files(
                    dirpath, metric, args.src_cloud, args.src_region, args.dst_cloud, args.dst_region)
                run_action(args, metric, values_and_weights_by_region_pair, dirpath)
        elif args.routes_distribution_tsvs:
            for routes_distribution_tsv in args.routes_distribution_tsvs:
                values_and_weights_by_region_pair = get_values_and_weights_by_region_pair_from_tsv(
                    routes_distribution_tsv, metric, args.src_cloud, args.src_region, args.dst_cloud, args.dst_region)
                run_action(args, metric, values_and_weights_by_region_pair, routes_distribution_tsv.name)
        else:
            raise ValueError('Either --dirpaths or --routes-distribution-tsvs must be specified')
        # Save the combined plot in case of CDF.
        if args.plot_cdf:
            label_cloud_region = get_label_from_cloud_region_pair(args.src_cloud, args.src_region,
                                                                  args.dst_cloud, args.dst_region)
            save_last_plot(metric, args.aggregate_each_region_pair_by, label_cloud_region)

if __name__ == '__main__':
    main()
