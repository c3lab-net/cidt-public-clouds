#!/usr/bin/env python3

import argparse
import logging
import pandas as pd

from common import get_routes_from_file, init_logging, load_itdk_node_ip_to_id_mapping

def parse_node_asn_as_dataframe(node_as_filename='../data/caida-itdk/midar-iff.nodes.as') -> pd.Series:
    """Parse the node AS file and return a series of AS numbers with the node ID as the index."""
    logging.info(f'Loading node geo entries from {node_as_filename} ...')
    columns = ['label', 'node_id', 'AS', 'heuristic_tag']
    column_dtypes = {
        'label': str,
        'node_id': str,
        'AS': int,
        'heuristic_tag': str,
    }
    usecols = ['node_id', 'AS']

    node_asn_df = pd.read_csv(node_as_filename, sep='\t', comment='#', index_col='node_id',
                              names=columns, dtype=column_dtypes, usecols=usecols)
    node_asn_ds = node_asn_df.squeeze()
    logging.info(f'Loaded {len(node_asn_ds)} entries from {node_as_filename}.')
    return node_asn_ds

def convert_routes_from_ip_to_asn(routes: list[list[str]], node_ip_to_id: dict[str, str], node_asn_ds: pd.Series):
    logging.info('Converting routes from IPs to AS numbers ...')
    converted_routes = []

    for ip_addresses in routes:
        # Convert each IP address to a node ID using the node_ip_to_id dictionary
        node_ids = [node_ip_to_id.get(ip, '') for ip in ip_addresses]

        # Convert node IDs to AS numbers using the node_as_ds series
        l_asn = []
        for node_id in node_ids:
            if not node_id:
                logging.warning(f'Ignoring unknown node with ip {ip_addresses}')
                continue
            # _debug_
            if node_id not in node_asn_ds.index:
                logging.error(f'Node ID {node_id} not found in node_as_ds')
                l_asn = []
                break
            asn = node_asn_ds[node_id]
            l_asn.append(asn)
        # _debug_
        if l_asn == []:
            continue

        # Append the converted route to the result
        print(l_asn)
        converted_routes.append(l_asn)

    logging.info('Done')
    return converted_routes

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The routes file, each line contains a list that represents a route.')
    parser.add_argument('--convert-ip-to-asn', action='store_true',
                        help='Convert the routes from IP addresses to AS numbers')
    args = parser.parse_args()

    if args.convert_ip_to_asn and args.routes_file is None:
        parser.error('routes_file must be specified when --convert-ip-to-asn is specified')

    return args

def main():
    init_logging()
    args = parse_args()
    if args.convert_ip_to_asn:
        routes = get_routes_from_file(args.routes_file)
        node_ip_to_id = load_itdk_node_ip_to_id_mapping()
        node_asn_ds = parse_node_asn_as_dataframe()
        routes_by_asn = convert_routes_from_ip_to_asn(routes, node_ip_to_id, node_asn_ds)
        # print(routes_by_asn)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()

