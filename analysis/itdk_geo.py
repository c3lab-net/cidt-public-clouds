#!/usr/bin/env python3

import argparse
import io
import logging
import sys
from typing import Optional
import pandas as pd

from common import get_routes_from_file, init_logging, load_itdk_node_ip_to_id_mapping

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

def convert_routes_from_ip_to_latlon(routes, node_ip_to_id, node_geo_df, output: Optional[io.TextIOWrapper] = None):
    logging.info('Converting routes from IPs to lat/lons ...')
    converted_routes = []

    for ip_addresses in routes:
        # Convert each IP address to a node ID using the node_ip_to_id dictionary
        node_ids = [node_ip_to_id.get(ip, '') for ip in ip_addresses]

        # Convert node IDs to latitude and longitude using the node_geo_df dictionary
        coordinates = []
        for node_id in node_ids:
            if not node_id:
                logging.warning(f'Ignoring unknown node with ip {ip_addresses}')
                continue
            # _debug_
            if node_id not in node_geo_df.index:
                logging.error(f'Node ID {node_id} not found in node_geo_df')
                coordinates = []
                break
            row = node_geo_df.loc[node_id]
            coordinates.append((row['lat'], row['long']))
        # _debug_
        if coordinates == []:
            continue

        # Append the converted route to the result
        print(coordinates, file=output if output else sys.stdout)
        converted_routes.append(coordinates)

    logging.info('Done')
    return converted_routes

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The routes file, each line contains a list that represents a route.')
    parser.add_argument('--convert-ip-to-latlon', action='store_true',
                        help='Convert the routes from IP addresses to lat/lon coordinates')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='The output file.')
    args = parser.parse_args()

    if args.convert_ip_to_latlon and args.routes_file is None:
        parser.error('routes_file must be specified when --convert-ip-to-latlon is specified')

    return args

def main():
    init_logging()
    args = parse_args()
    if args.convert_ip_to_latlon:
        routes = get_routes_from_file(args.routes_file)
        node_ip_to_id = load_itdk_node_ip_to_id_mapping()
        node_geo_df = parse_node_geo_as_dataframe()
        convert_routes_from_ip_to_latlon(routes, node_ip_to_id, node_geo_df, args.output)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()

