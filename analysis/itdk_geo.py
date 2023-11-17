#!/usr/bin/env python3

import argparse
import csv
import io
import logging
import os
import sys
import traceback
from typing import Callable, Optional
import pandas as pd

from common import detect_cloud_regions_from_filename, get_routes_from_file, init_logging, load_itdk_node_ip_to_id_mapping

def parse_node_geo_as_dataframe(node_geo_filename='../data/caida-itdk/midar-iff.nodes.geo'):
    logging.info(f'Loading node geo entries from {node_geo_filename} ...')
    columns = ['node_id', 'continent', 'country', 'region', 'city', 'lat', 'long', 'pop', 'IX', 'source']
    column_dtypes = {
        # 'node_id': None,  # type is already specified by the converter
        'continent': str,
        'country': str,
        'region': str,
        'city': str,
        'lat': float,
        'long': float,
        'pop': str,
        'IX': str,
        'source': str,
    }
    usecols = ['node_id', 'continent', 'country', 'region', 'city', 'lat', 'long']
    converter_node_id = lambda s: s.removeprefix('node.geo ').removesuffix(':')

    node_geo_df = pd.read_csv(node_geo_filename, sep='\t', comment='#', index_col='node_id',
                              names=columns, dtype=column_dtypes, usecols=usecols,
                              converters={'node_id': converter_node_id })
    logging.info(f'Loaded {len(node_geo_df)} entries from {node_geo_filename}.')
    return node_geo_df

def get_node_ids_with_geo_coordinates():
    node_geo_df = parse_node_geo_as_dataframe()
    return node_geo_df.index.tolist()

def convert_routes_from_ip_to_latlon(routes, node_ip_to_id, node_geo_df,
                                     is_valid_route: Callable[[list[tuple[float, float]]], bool],
                                     output_file: Optional[str]):
    logging.info('Converting valid routes from IPs to lat/lons ...')
    converted_routes = []

    if output_file:
        output = open(output_file, 'w')
        logging.info(f'Writing (lat, lon) routes to {output_file} ...')
    else:
        output = None
    for ip_addresses in routes:
        # Convert each IP address to a node ID using the node_ip_to_id dictionary
        node_ids = [node_ip_to_id.get(ip, '') for ip in ip_addresses]

        # Convert node IDs to latitude and longitude using the node_geo_df dictionary
        coordinates = []
        for node_id in node_ids:
            if not node_id:
                logging.warning(f'Ignoring unknown node with ip {ip_addresses}')
                continue
            if node_id not in node_geo_df.index:
                logging.error(f'Node ID {node_id} not found in node_geo_df')
                coordinates = []
                break
            row = node_geo_df.loc[node_id]
            coordinates.append((row['lat'], row['long']))
        # Route must have at least 2 hops, at src and dst.
        if len(coordinates) < 2:
            logging.warning(f'Ignoring route with less than 2 hops: {ip_addresses}')
            continue

        # Check if the route is valid
        if not is_valid_route(coordinates):
            continue

        # Append the converted route to the result
        print(coordinates, file=output if output else sys.stdout)
        converted_routes.append(coordinates)

    if output:
        output.close()

    logging.info('Converted/Total: %d/%d', len(converted_routes), len(routes))
    return converted_routes

def load_region_to_geo_coordinate_ground_truth(geo_coordinate_ground_truth_csv: io.TextIOWrapper):
    with geo_coordinate_ground_truth_csv as f:
        csv_reader = csv.DictReader(f)
        d_region_to_coordinate = {}
        for row in csv_reader:
            region_key = f"{row['cloud']}:{row['region']}"
            coordinates = (float(row['latitude']), float(row['longitude']))
            d_region_to_coordinate[region_key] = coordinates
    return d_region_to_coordinate

def get_route_check_function_by_ground_truth(geo_coordinate_ground_truth: dict[str, tuple[float, float]],
                                             src_cloud: str, src_region: str,
                                             dst_cloud: str, dst_region: str) -> \
                                                Callable[[list[tuple[float, float]]], bool]:
        src = f'{src_cloud}:{src_region}'
        dst = f'{dst_cloud}:{dst_region}'
        try:
            src_coordinate = geo_coordinate_ground_truth[src]
            dst_coordinate = geo_coordinate_ground_truth[dst]
        except KeyError as ex:
            logging.error(f'KeyError: {ex}')
            logging.error(traceback.format_exc())
            raise ValueError(f'Region not found in ground truth CSV: {ex}')

        logging.info('Filtering routes based on ground truth geo coordinates of src and dst ...')
        logging.info(f'Ground truth: src: {src} -> {src_coordinate}, dst: {dst} -> {dst_coordinate}')
        check_route_by_ground_truth = lambda route: route[0] == src_coordinate and route[-1] == dst_coordinate
        return check_route_by_ground_truth

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_files', type=str, nargs='+', help='The routes file, each line contains a list that represents a route.')
    parser.add_argument('--convert-ip-to-latlon', action='store_true',
                        help='Convert the routes from IP addresses to lat/lon coordinates')
    parser.add_argument('-o', '--outputs', type=str, nargs='*', help='The output file.')
    parser.add_argument('--filter-geo-coordinate-by-ground-truth', action='store_true',
                        help='Filter the routes by ground truth geo coordinates.')
    parser.add_argument('--geo-coordinate-ground-truth-csv', type=argparse.FileType('r'),
                        help='The CSV file containing the ground truth geo coordinates.')
    parser.add_argument('--src-cloud', required=False, help='The source cloud')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud')
    parser.add_argument('--src-region', required=False, help='The source region')
    parser.add_argument('--dst-region', required=False, help='The destination region')
    args = parser.parse_args()

    if not args.convert_ip_to_latlon:
        parser.error('No action specified. Please specify --convert-ip-to-latlon')

    if args.convert_ip_to_latlon and args.routes_files is None:
        parser.error('routes_files must be specified when --convert-ip-to-latlon is specified')

    if args.outputs is not None and len(args.outputs) not in [0, len(args.routes_files)]:
        parser.error('The number of output files must match the number of routes files, or be 0 (auto-naming files)')

    if args.filter_geo_coordinate_by_ground_truth:
        if not args.geo_coordinate_ground_truth_csv:
            parser.error('--geo-coordinate-ground-truth-csv must be specified when --filter-geo-coordinate-by-ground-truth is specified')
        args.cloud_region_pair_by_filename = {}
        if not args.src_cloud and not args.dst_cloud and not args.src_region and not args.dst_region:
            # Check if we can auto-detect the src and dst cloud/region from the routes files
            for routes_file in args.routes_files:
                cloud_regions = detect_cloud_regions_from_filename(routes_file)
                if cloud_regions is None:
                    parser.error('Cannot auto-detect cloud regions from the filename "%s"' % routes_file)
                else:
                    logging.info(f'Auto-detected cloud regions from filename "{routes_file}": {cloud_regions}')
                    args.cloud_region_pair_by_filename[routes_file] = cloud_regions
        else:
            if not args.src_cloud:
                parser.error('--src-cloud must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.dst_cloud:
                parser.error('--dst-cloud must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.src_region:
                parser.error('--src-region must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.dst_region:
                parser.error('--dst-region must be specified when --filter-geo-coordinate-by-ground-truth is specified')

    return args

def main():
    init_logging()
    args = parse_args()
    if args.convert_ip_to_latlon:
        node_ip_to_id = load_itdk_node_ip_to_id_mapping()
        node_geo_df = parse_node_geo_as_dataframe()
        geo_coordinate_ground_truth = \
            load_region_to_geo_coordinate_ground_truth(args.geo_coordinate_ground_truth_csv) \
            if args.filter_geo_coordinate_by_ground_truth else {}
        for i in range(len(args.routes_files)):
            routes_file: str = args.routes_files[i]
            # Auto-name output_file
            if args.outputs is not None:
                if len(args.outputs) == 0:
                    output_file = os.path.basename(routes_file).removesuffix('.by_ip') + '.by_geo'
                else:
                    output_file = args.outputs[i]
            else:
                output_file = None
            # Generate check route function
            if args.filter_geo_coordinate_by_ground_truth:
                if routes_file in args.cloud_region_pair_by_filename:
                    (src_cloud, src_region, dst_cloud, dst_region) = args.cloud_region_pair_by_filename[routes_file]
                else:
                    (src_cloud, src_region) = (args.src_cloud, args.src_region)
                    (dst_cloud, dst_region) = (args.dst_cloud, args.dst_region)
                check_route_by_ground_truth = \
                    get_route_check_function_by_ground_truth(geo_coordinate_ground_truth,
                                                            src_cloud, src_region,
                                                            dst_cloud, dst_region)
            else:
                check_route_by_ground_truth = lambda _: True
            # Convert routes
            logging.info(f'Converting routes from {routes_file} to {output_file if output_file else "stdout"} ...')
            routes = get_routes_from_file(routes_file)
            convert_routes_from_ip_to_latlon(routes, node_ip_to_id, node_geo_df,
                                             check_route_by_ground_truth,
                                             output_file)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()

