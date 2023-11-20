#!/usr/bin/env python3

import argparse
import ast
import logging
import os
import re
import functools
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from geopy.distance import geodesic
from typing import Any, Callable, Optional

from common import DirType, init_logging

DATA_SOURCE = 'caida.itdk'


def load_weighted_hops(file_path: str) -> pd.DataFrame:
    """Load the file that contains a list of weights and hops.

        File format:
        4 hop1|hop2|hop3
        1 hop1|hop2
        ...
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()

    # Split each line into two parts
    l_weight = []
    l_hops = []
    for line in lines:
        parts = line.strip().split(' ', 1)
        weight = float(parts[0])
        hops = parts[1]
        l_weight.append(weight)
        l_hops.append(hops)

    # Create a DataFrame
    return pd.DataFrame.from_dict({'weight': l_weight, 'hops': l_hops})

def calculate_total_distance(hops: list[str]) -> float:
    """Calculate the total distance across all hops.

        Each hop is represented as a string of the form: '(lat,lon)'
    """
    if len(hops) <= 1:
        return 0.

    @functools.cache
    def calculate_pairwise_distance_km(hop1: str, hop2: str) -> float:
        (lat1, lon1) = ast.literal_eval(hop1)
        (lat2, lon2) = ast.literal_eval(hop2)
        return geodesic((lat1, lon1), (lat2, lon2)).km

    total_distance = 0.
    for i in range(len(hops) - 1):
        total_distance += calculate_pairwise_distance_km(hops[i], hops[i + 1])
    return total_distance

def get_hops_and_weights(file_path: str) -> tuple[np.ndarray, np.ndarray]:
    data = load_weighted_hops(file_path)
    hops = data['hops'].to_numpy()
    weights = data['weight'].to_numpy()
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

def plot_pdf(values, weights, src_region: str, dst_region: str, metric: str, data_source: str):
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

def plot_heatmap(src_regions: list[str], dst_regions: list[str], region_hop_counts: dict[tuple[str, str], float],
                 metric: str, data_source: str):
    # Create a mapping of regions to indices
    src_region_to_index = {region: index for index, region in enumerate(src_regions)}
    dst_region_to_index = {region: index for index, region in enumerate(dst_regions)}

    # Initialize a matrix for the data
    matrix = np.zeros((len(src_regions), len(dst_regions)))

    # Populate the matrix
    for (src_region, dst_region), value in region_hop_counts.items():
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

def get_weighted_average_by_region_pair(dirpath: str, process_hops: Callable[[list[str]], Any],
                                        metric: str, plot_pdfs: bool,
                                        src_cloud: Optional[str], src_region: Optional[str],
                                        dst_cloud: Optional[str], dst_region: Optional[str]):
    # Dictionary to hold the source-destination pairs and the aggregated value
    weighted_average_by_region_pair = {}

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
        values = np.array(list(map(process_hops, hops)))

        # Skip bad values
        for i in range(values.size):
            # Ignore the distance if it is 0
            if values[i] == 0.:
                weights[i] = 0.

        src = ':'.join(src)
        dst = ':'.join(dst)
        weighted_average_by_region_pair[(src, dst)] = np.average(values, weights=weights).tolist()

        if plot_pdfs:
            plot_pdf(values, weights, src, dst, metric, DATA_SOURCE)
    return weighted_average_by_region_pair

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--metrics', choices=['hopcount', 'distance'], required=True, nargs='+',
                        help='The metrics to plot')
    parser.add_argument('--dirpath', type=DirType, required=True, help='The directory that contains the routes files')
    parser.add_argument('--plot-heatmap', action='store_true',
                        help='Plot the heatmap of the metric across all region pairs')
    parser.add_argument('--plot-pdfs', action='store_true',
                        help='Plot the PDFs of the metric, one graph for each region pair')
    parser.add_argument('--src-cloud', required=False, help='The source cloud to filter on')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud to filter on')
    parser.add_argument('--src-region', required=False, help='The source region to filter on')
    parser.add_argument('--dst-region', required=False, help='The destination region to filter on')
    args = parser.parse_args()

    if not (args.plot_heatmap or args.plot_pdfs):
        parser.error('At least one of --plot-heatmap or --plot-pdfs must be specified')

    if args.src_region and not args.src_cloud:
        parser.error('--src-cloud must be specified with --src-region')

    if args.dst_region and not args.dst_cloud:
        parser.error('--dst-cloud must be specified with --dst-region')

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()

    for metric in args.metrics:
        if metric == 'hopcount':
            process_hops = lambda x: len(x.split('|'))
        elif metric == 'distance':
            process_hops = lambda x: calculate_total_distance(x.split('|'))
        else:
            raise NotImplementedError(f'Unknown metric: {metric}')
        value_by_region_pair = get_weighted_average_by_region_pair(args.dirpath, process_hops, metric, args.plot_pdfs,
                                                                   args.src_cloud, args.src_region,
                                                                   args.dst_cloud, args.dst_region)
        src_dst_pairs = value_by_region_pair.keys()
        src_regions = sorted(set(t[0] for t in src_dst_pairs))
        dst_regions = sorted(set(t[1] for t in src_dst_pairs))
        if args.plot_heatmap:
            plot_heatmap(src_regions, dst_regions, value_by_region_pair, metric, DATA_SOURCE)

if __name__ == '__main__':
    main()
