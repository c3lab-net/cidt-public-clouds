#!/usr/bin/env python3

import argparse
import ast
from collections import Counter
import csv
import io
import logging
import sys
from typing import Any, Optional

import pandas as pd

from common import RouteMetric, calculate_route_metric, get_routes_from_file, init_logging

PHYSICAL_ROUTE_REQUIRED_METRICS = [
    RouteMetric.FiberWktPaths,
    RouteMetric.FiberTypes,
]

def remove_duplicate_consecutive_hops(route: list[Any]):
    prev_hop = None
    i = 0
    # Keep at least 2 hops, aka source and destination.
    while i < len(route):
        hop = route[i]
        if hop == prev_hop:
            del route[i]
        else:
            prev_hop = hop
            i += 1
    if len(route) == 1:
        route.append(route[0])

def load_physical_routes_tsv(physical_routes_file: io.TextIOWrapper) -> dict[str, dict]:
    physical_route_info = {}
    FIELDNAMES = ['routers_latlon', 'distance_km', 'fiber_wkt_paths', 'fiber_types']
    for metric in RouteMetric:
        physical_route_info[metric] = {}
    with physical_routes_file as f:
        csv_reader = csv.DictReader(f, delimiter='\t', fieldnames=FIELDNAMES)
        for row in csv_reader:
            routers_latlon = ast.literal_eval(row['routers_latlon'])
            route_id = '|'.join([str(e) for e in routers_latlon])
            physical_route_info[RouteMetric.HopCount][route_id] = len(routers_latlon)
            physical_route_info[RouteMetric.DistanceKM][route_id] = float(row['distance_km'])
            physical_route_info[RouteMetric.FiberWktPaths][route_id] = row['fiber_wkt_paths']
            physical_route_info[RouteMetric.FiberTypes][route_id] = row['fiber_types']
    return physical_route_info

def lookup_physical_route_metric(route: str, metric: RouteMetric, physical_route_info: dict[str, dict]):
    try:
        return physical_route_info[metric][route]
    except KeyError as ex:
        raise ValueError(f'Route {route} not found in physical route info') from ex

def calculate_routes_distribution(routes: list[list], metrics:list[RouteMetric],
                                  physical_route_info: Optional[dict[str, dict]] = None) -> pd.DataFrame:
    logging.info('Calculating routes distribution ...')

    columns = ['count'] + [metric for metric in metrics] + ['route']

    routes_as_str = [ '|'.join([str(e) for e in route]) for route in routes ]
    rows = []
    for route_str, count in sorted(Counter(routes_as_str).items(), key=lambda x: x[1], reverse=True):
        row: list[Any] = [count]
        for metric in metrics:
            if physical_route_info is not None and metric in physical_route_info:
                value = lookup_physical_route_metric(route_str, metric, physical_route_info)
            else:
                value = calculate_route_metric(route_str, metric)
            row.append(value)
        row.append(route_str)
        rows.append(row)

    df = pd.DataFrame(rows, columns=columns)

    logging.info('Done')

    return df

def export_routes_distribution(routes_distribution: pd.DataFrame,
                               output: Optional[io.TextIOWrapper] = None,
                               header: bool = False) -> None:
    routes_distribution.to_csv(output if output else sys.stdout, sep='\t', index=False, header=header)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, required=True, help='The routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('--remove-duplicate-consecutive-hops', action='store_true',
                        help='Remove duplicate consecutive hops from the routes.')
    parser.add_argument('--export-routes-distribution', required=True, action='store_true',
                        help='Export the routes distribution.')
    parser.add_argument('--no-header', action='store_true', help='Do not include the header in the output.')
    parser.add_argument('--include', nargs='*', type=RouteMetric, choices=list(RouteMetric),
                        help='The additional metrics to include.')
    parser.add_argument('--physical-routes-tsv', type=argparse.FileType('r'),
                        help='The physical routes TSV file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('-o', '--output-tsv', type=argparse.FileType('w'), help='The output TSV file.')
    args = parser.parse_args()

    if not args.include:
        args.include = []

    if any([metric in PHYSICAL_ROUTE_REQUIRED_METRICS for metric in args.include]) and not args.physical_routes_tsv:
        parser.error('Physical routes TSV file is required if physical hop metrics are included.')

    if args.remove_duplicate_consecutive_hops and args.physical_routes_tsv:
        # TODO: move remove-duplicate-consecutive-hops to the previous step.
        parser.error('Cannot remove duplicate consecutive hops if physical routes TSV file is provided.')

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()

    if args.export_routes_distribution:
        routes = get_routes_from_file(args.routes_file)
        if args.remove_duplicate_consecutive_hops:
            for route in routes:
                remove_duplicate_consecutive_hops(route)
        physical_route_info = load_physical_routes_tsv(args.physical_routes_tsv) if args.physical_routes_tsv else None
        routes_distribution = calculate_routes_distribution(routes, args.include, physical_route_info)
        export_routes_distribution(routes_distribution, args.output_tsv, not args.no_header)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
