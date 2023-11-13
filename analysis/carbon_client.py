#!/usr/bin/env python3

import argparse
from collections import Counter
import csv
import io
import logging
import sys
import traceback
from typing import Optional

import requests_cache

from common import get_routes_from_file, CARBON_API_URL, init_logging

session = requests_cache.CachedSession('carbon_cache', backend='filesystem')

def get_carbon_region_from_coordinate(coordinate: tuple[float, float]):
    (latitude, longitude) = coordinate
    response = session.get(f'{CARBON_API_URL}/balancing-authority/', params={
        'latitude': latitude,
        'longitude': longitude,
        'iso_format': 'emap',
    })
    try:
        assert response.ok, "Carbon region lookup failed for %s (%d): %s" % (coordinate, response.status_code, response.text)
        response_json = response.json()
        assert 'iso' in response_json, 'Invalid carbon region lookup response %s: %s' % (coordinate, response.text)
        return response_json['iso']
    except Exception as ex:
        logging.error(ex)
        logging.error(traceback.format_exc())
        return 'Unknown'

def convert_latlon_to_carbon_region(routes: list[list[tuple[float, float]]], output: Optional[io.TextIOWrapper] = None):
    logging.info('Converting lat/lon to carbon region ...')
    coordinates = set()
    for route in routes:
        for coordinate in route:
            coordinates.add(coordinate)

    d_coordinate_to_carbon_region = {}
    for coordinate in coordinates:
        d_coordinate_to_carbon_region[coordinate] = get_carbon_region_from_coordinate(coordinate)

    routes_in_carbon_region = []
    for route in routes:
        route_in_carbon_region = []
        for coordinate in route:
            carbon_region = d_coordinate_to_carbon_region[coordinate]
            route_in_carbon_region.append(carbon_region)
        routes_in_carbon_region.append(route_in_carbon_region)
        print(route_in_carbon_region, file=output if output else sys.stdout)
    return routes_in_carbon_region

def load_region_to_iso_groud_truth(iso_ground_truth_csv: str):
    with open(iso_ground_truth_csv, 'r') as f:
        csv_reader = csv.DictReader(f)
        d_region_to_iso = { f"{row['cloud']}:{row['region']}": row['iso'] for row in csv_reader }
    return d_region_to_iso

def filter_iso_by_ground_truth(routes: list[list], src_cloud: str, dst_cloud: str,
                               src_region: str, dst_region: str,
                               iso_ground_truth: dict[str, str]) -> list[list]:
    """Filter the routes by ground truth ISOs of the src and dst regions, aka the first and last hop."""
    logging.info('Filtering ISO by ground truth ...')

    src_iso = iso_ground_truth[f'{src_cloud}:{src_region}']
    dst_iso = iso_ground_truth[f'{dst_cloud}:{dst_region}']

    filtered_routes = []
    for route in routes:
        if routes and route[0] == src_iso and route[-1] == dst_iso:
            filtered_routes.append(route)

    logging.info('Filtered/Total: %d/%d', len(filtered_routes), len(routes))
    return filtered_routes

def export_routes_distribution(routes: list[list], output: Optional[io.TextIOWrapper] = None):
    logging.info('Exporting routes distribution ...')

    routes_as_str = [ '|'.join([str(e) for e in route]) for route in routes ]
    for route_str, count in sorted(Counter(routes_as_str).items(), key=lambda x: x[1], reverse=True):
        print(count, route_str, file=output if output else sys.stdout)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='The output file.')
    parser.add_argument('--convert-latlon-to-carbon-region', action='store_true',
                        help='Convert the routes from lat/lon coordinates to Carbon region names.')
    parser.add_argument('--export-routes-distribution', action='store_true',
                        help='Export the routes distribution.')
    parser.add_argument('--filter-iso-by-ground-truth', action='store_true', help='Filter the routes by ground truth ISOs.')
    parser.add_argument('--iso-ground-truth-csv', type=str, help='The CSV file containing the ground truth ISOs.')
    parser.add_argument('--src-cloud', required=False, help='The source cloud')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud')
    parser.add_argument('--src-region', required=False, help='The source region')
    parser.add_argument('--dst-region', required=False, help='The destination region')
    args = parser.parse_args()

    if (args.convert_latlon_to_carbon_region or args.export_routes_distribution) and args.routes_file is None:
        parser.error('routes_file must be specified when --convert-latlon-to-carbon-region or --export-routes-distribution is specified')

    if args.filter_iso_by_ground_truth:
        if not args.export_routes_distribution:
            parser.error('--filter-iso-by-ground-truth can only be used with --export-routes-distribution')
        if not args.iso_ground_truth_csv:
            parser.error('--iso-ground-truth-csv must be specified when --filter-iso-by-ground-truth is specified')
        if not args.src_cloud:
            parser.error('--src-cloud must be specified when --filter-iso-by-ground-truth is specified')
        if not args.dst_cloud:
            parser.error('--dst-cloud must be specified when --filter-iso-by-ground-truth is specified')
        if not args.src_region:
            parser.error('--src-region must be specified when --filter-iso-by-ground-truth is specified')
        if not args.dst_region:
            parser.error('--dst-region must be specified when --filter-iso-by-ground-truth is specified')

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()
    if args.convert_latlon_to_carbon_region:
        routes = get_routes_from_file(args.routes_file)
        convert_latlon_to_carbon_region(routes, args.output)
    elif args.export_routes_distribution:
        routes = get_routes_from_file(args.routes_file)
        if args.filter_iso_by_ground_truth:
            iso_ground_truth = load_region_to_iso_groud_truth(args.iso_ground_truth_csv)
            routes = filter_iso_by_ground_truth(routes, args.src_cloud, args.dst_cloud,
                                                args.src_region, args.dst_region, iso_ground_truth)
        export_routes_distribution(routes, args.output)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
