#!/usr/bin/env python3

import argparse
import ast
import itertools
import logging
import re
import sys
import time

from common import MATCHED_NODES_FILENAME_AWS, MATCHED_NODES_FILENAME_GCLOUD, init_logging, load_itdk_node_id_to_ips_mapping
from itdk_geo import get_node_ids_with_geo_coordinates
from graph_module import Graph

import socket
import struct

def ip_to_unsigned_int(ip: str) -> int:
    packed_ip = socket.inet_aton(ip)
    return struct.unpack("!I", packed_ip)[0]

def unsigned_int_to_ip(unsigned_int: int) -> str:
    packed_ip = struct.pack("!I", unsigned_int)
    return socket.inet_ntoa(packed_ip)

def load_itdk_graph_from_links(itdk_node_id_to_ips: dict[str, list], link_file='../data/caida-itdk/midar-iff.links') -> Graph:
    logging.info('Building graph from ITDK nodes/links ...')

    logging.info('Loading links from file to memory ...')
    start_time = time.time()
    with open(link_file) as file:
        all_lines = file.readlines()
    elapsed_time = time.time() - start_time
    logging.info(f'Elapsed: {elapsed_time}s, read {len(all_lines)} lines.')

    graph = Graph()
    graph.reserve(len(itdk_node_id_to_ips))
    edge_count = 0
    re_link = re.compile(r'^link L(?:\d+): +([N\d.: ]+)')

    logging.info('Building adjacency list graph in memory ...')
    start_time = time.time()
    for line in all_lines:
        if line.startswith('#'):
            continue

        m = re_link.match(line)
        if not m:
            print('Cannot process line:', line, file=sys.stderr)
            continue
        routers = m.group(1)
        known_interfaces = set()
        for router in routers.split():
            # router is either Nxxx:1.2.3.4 (known interface) or Nxxxx (inferred interface).
            # There's no links at IP level from known interface only, using inferred interface.
            #   More detail: https://publicdata.caida.org/datasets/topology/ark/ipv4/itdk/2022-02/ under .links
            # Because geo information is only tied to node ID, we need to use node ID to find the IP addresses.
            node_id = router.split(':', 1)[0]
            router_ips = itdk_node_id_to_ips.get(node_id, [])
            for router_ip in router_ips:
                known_interfaces.add(router_ip)
        if len(known_interfaces) <= 1:
            continue
        # print(f'Found interfaces: {known_interfaces}', file=sys.stderr)
        for (n1, n2) in itertools.combinations(known_interfaces, 2):
            graph.add_edge(ip_to_unsigned_int(n1), ip_to_unsigned_int(n2))

        edge_count += 1
        if edge_count % 1000000 == 0:
            elapsed_time = time.time() - start_time
            logging.debug(f'Elapsed: {elapsed_time}s, edge count: {edge_count}')
            # break   # _debug_
    elapsed_time = time.time() - start_time
    logging.info(f'Elapsed: {elapsed_time:.2f}s, total edge count: {edge_count}')
    return graph

def get_cloud_region_matched_ips(cloud: str, region: str) -> list[str]:
    if cloud == 'aws':
        matched_nodes_filename = MATCHED_NODES_FILENAME_AWS
    elif cloud == 'gcloud':
        matched_nodes_filename = MATCHED_NODES_FILENAME_GCLOUD
    else:
        raise ValueError(f'Unsupported cloud {cloud}')

    with open(matched_nodes_filename) as file:
        dict_str = file.read()
        d_by_region = ast.literal_eval(dict_str)
    if region:
        if region not in d_by_region:
            raise ValueError(f'Region {region} not found in {cloud}')
        d_node_to_matches = d_by_region[region]
    else:
        # Merge all regions together
        d_node_to_matches = {}
        for region in d_by_region:
            d_node_to_matches.update(d_by_region[region])

    ips = []
    for node_id in d_node_to_matches:
        for ip_prefix, ip in d_node_to_matches[node_id]:
            # logging.debug(node_id, ip_prefix, ip)
            ips.append(ip)
    logging.info(f'Found {len(ips)} IPs for {cloud}:{region}.')
    return ips

def remove_node_without_geo_coordinates(itdk_node_id_to_ips: dict):
    nodes_with_geo_coordinates = set(get_node_ids_with_geo_coordinates())
    removed_count = 0

    logging.info('Removing nodes without geocoordinates ...')
    processed_count = 0
    start_time = time.time()
    for node_id in itdk_node_id_to_ips.copy().keys():
        if node_id not in nodes_with_geo_coordinates:
            del itdk_node_id_to_ips[node_id]
            removed_count += 1

        processed_count += 1
        if processed_count % 1000000 == 0:
            elapsed_time = time.time() - start_time
            logging.debug(f'Elapsed: {elapsed_time:.2f}s, node count: {processed_count}')
    logging.info(f'Removed {removed_count} nodes without geocoordinates.')

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src-cloud', required=False, choices=[ 'aws', 'gcloud' ], help='The source cloud provider')
    parser.add_argument('--dst-cloud', required=False, choices=[ 'aws', 'gcloud' ], help='The destination cloud provider')
    parser.add_argument('--src-regions', type=str, nargs='+', required=False, help='The source regions')
    parser.add_argument('--dst-regions', type=str, nargs='+', required=False, help='The destination regions')

    parser.add_argument('--src-nodes', required=False, nargs='+', help='The source node ids')
    parser.add_argument('--dst-nodes', required=False, nargs='+', help='The destination node ids')

    parser.add_argument('--src-ips', required=False, nargs='+', help='The source IP addresses')
    parser.add_argument('--dst-ips', required=False, nargs='+', help='The destination IP addresses')

    # Must provide one of src/dst cloud, ips or nodes
    args = parser.parse_args()
    if not (args.src_cloud or args.src_ips or args.src_nodes):
        parser.error('Must provide one of --src-cloud, --src-ips or --src-nodes')
    if not (args.dst_cloud or args.dst_ips or args.dst_nodes):
        parser.error('Must provide one of --dst-cloud, --dst-ips or --dst-nodes')

    return parser.parse_args()

def load_ips_in_groups(cloud: str, regions: list[str], ips: list[str]) -> dict[str, list[str]]:
    """Load IPs in a set of regions, for later batched execution."""
    if regions:
        return { f'{cloud}:{region}': get_cloud_region_matched_ips(cloud, region) for region in regions }
    elif ips:
        return { '': ips }
    else:
        return {}

def main():
    init_logging()
    args = parse_args()
    src_ips_groups = load_ips_in_groups(args.src_cloud, args.src_regions, args.src_ips)
    dst_ips_groups = load_ips_in_groups(args.dst_cloud, args.dst_regions, args.dst_ips)

    # Build graph from ITDK nodes/links
    itdk_node_id_to_ips = load_itdk_node_id_to_ips_mapping()
    remove_node_without_geo_coordinates(itdk_node_id_to_ips)
    graph = load_itdk_graph_from_links(itdk_node_id_to_ips)

    # Load the set of source and destination IPs
    if not src_ips_groups:
        src_ips_groups = { '': [ip for node_id in args.src_nodes for ip in itdk_node_id_to_ips[node_id]] }
    if not dst_ips_groups:
        dst_ips_groups = { '': [ip for node_id in args.dst_nodes for ip in itdk_node_id_to_ips[node_id]] }

    for src_group in src_ips_groups:
        for dst_group in dst_ips_groups:
            # Skip same region routes
            if src_group and src_group == dst_group:
                continue

            src_ips = [ip_to_unsigned_int(item) for item in src_ips_groups[src_group]]
            dst_ips = [ip_to_unsigned_int(item) for item in dst_ips_groups[dst_group]]

            # Run Dijkstra in parallel
            logging.info(f'Finding paths from {src_group} to {dst_group} ...')
            logging.info(f'Source IP count: {len(src_ips)}, destination IP count: {len(dst_ips)}')
            start_time = time.time()
            paths = graph.parallelDijkstra(src_ips, set(dst_ips))
            elapsed_time = time.time() - start_time
            logging.info(f'Elapsed: {elapsed_time}s')

            print(f'# {src_group} -> {dst_group}')
            paths = [[unsigned_int_to_ip(item) for item in path] for path in paths if path]
            for path in paths:
                print(path)

            logging.info(f'Dijkstra from {src_group} to {dst_group} completed. Found {len(paths)} paths in total.')

if __name__ == '__main__':
    main()
