#!/usr/bin/env python3

import argparse
import ast
import itertools
import re
import sys
import heapq
import time

from typing import Any

from common import load_itdk_node_id_to_ips_mapping
from itdk_geo import get_node_ids_with_geo_coordinates

class Graph:
    def __init__(self):
        self.graph = {}

    def add_edge(self, u, v):
        if u not in self.graph:
            self.graph[u] = []
        self.graph[u].append(v)
        if v not in self.graph:
            self.graph[v] = []
        self.graph[v].append(u)

    def dijkstra(self, start, destinations: set = set()):
        if start in destinations:
            return [start]

        min_heap: list[tuple[float, Any]] = [(0, start)]
        distances = {node: float('inf') for node in self.graph}
        distances[start] = 0
        prev = {}
        current_node = None

        while min_heap:
            _, current_node = heapq.heappop(min_heap)
            if current_node in destinations:
                break

            for neighbor in self.graph.get(current_node, []):
                distance = distances[current_node] + 1

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    heapq.heappush(min_heap, (distance, neighbor))
                    prev[neighbor] = current_node

        if current_node not in prev:
            return None

        path = [current_node]
        while current_node != start:
            current_node = prev[current_node]
            path.append(current_node)
        path.reverse()

        return path

def load_itdk_graph_from_links(itdk_node_id_to_ips: dict[str, list], link_file='../data/caida-itdk/midar-iff.links') -> Graph:
    print('Building graph from ITDK nodes/links ...', file=sys.stderr)
    graph = Graph()
    edge_count = 0
    start_time = time.time()
    re_link = re.compile(r'^link L(?:\d+): +([N\d.: ]+)')
    with open(link_file, 'r') as file:
        for line in file:
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

                # # Without geo constraint, we can use this:
                # splitted = router.split(':', 1)
                # if len(splitted) > 1:
                #     router_ip = splitted[1]
                #     router_ips = [router_ip]
                # else:
                #     router_ips = itdk_node_id_to_ips.get(router, [])
                #     # if len(router_ips) == 0:
                #     #     print(f'WARNING: node {router} not found!', file=sys.stderr)
                for router_ip in router_ips:
                    known_interfaces.add(router_ip)
            if len(known_interfaces) <= 1:
                continue
            # print(f'Found interfaces: {known_interfaces}', file=sys.stderr)
            for (n1, n2) in itertools.combinations(known_interfaces, 2):
                graph.add_edge(n1, n2)

            edge_count += 1
            if edge_count % 1000000 == 0:
                elapsed_time = time.time() - start_time
                print(f'Elapsed: {elapsed_time}s, edge count: {edge_count}', file=sys.stderr)
                # break   # _debug_
    elapsed_time = time.time() - start_time
    print(f'Elapsed: {elapsed_time}s, total edge count: {edge_count}', file=sys.stderr)
    return graph

def get_cloud_region_matched_ips(cloud, region) -> list[str]:
    if cloud == 'aws':
        matched_nodes_filename = 'matched_nodes.aws.by_region.txt'
    elif cloud == 'gcloud':
        matched_nodes_filename = 'matched_nodes.gcloud.by_region.txt'
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
            # print(node_id, ip_prefix, ip, file=sys.stderr)    # _debug_
            ips.append(ip)
    print(f'Found {len(ips)} IPs for {cloud}:{region}.', file=sys.stderr)
    return ips

def remove_node_without_geo_coordinates(itdk_node_id_to_ips: dict):
    print('Removing nodes without geocoordinates ...', file=sys.stderr)
    nodes_with_geo_coordinates = set(get_node_ids_with_geo_coordinates())
    removed_count = 0

    processed_count = 0
    start_time = time.time()
    for node_id in itdk_node_id_to_ips.copy().keys():
        if node_id not in nodes_with_geo_coordinates:
            del itdk_node_id_to_ips[node_id]
            removed_count += 1

        processed_count += 1
        if processed_count % 1000000 == 0:
            elapsed_time = time.time() - start_time
            print(f'Elapsed: {elapsed_time}s, node count: {processed_count}', file=sys.stderr)
    print(f'Removing {removed_count} nodes without geocoordinates.', file=sys.stderr)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--src-cloud', required=False, choices=[ 'aws', 'gcloud' ], help='The source cloud provider')
    parser.add_argument('--dst-cloud', required=False, choices=[ 'aws', 'gcloud' ], help='The destination cloud provider')
    parser.add_argument('--src-region', required=False, help='The source region')
    parser.add_argument('--dst-region', required=False, help='The destination region')

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

def main():
    args = parse_args()
    if args.src_cloud:
        src_ips = get_cloud_region_matched_ips(args.src_cloud, args.src_region)
    elif args.src_ips:
        src_ips = args.src_ips
    else:
        src_ips = []
    if args.dst_cloud:
        dst_ips = get_cloud_region_matched_ips(args.dst_cloud, args.dst_region)
    elif args.dst_ips:
        dst_ips = list(args.dst_ips)
    else:
        dst_ips = []

    # Build graph from ITDK nodes/links
    itdk_node_id_to_ips = load_itdk_node_id_to_ips_mapping()
    remove_node_without_geo_coordinates(itdk_node_id_to_ips)
    graph = load_itdk_graph_from_links(itdk_node_id_to_ips)

    if not src_ips:
        src_ips = [ip for node_id in args.src_nodes for ip in itdk_node_id_to_ips[node_id]]

    print(f'Finding paths from {args.src_cloud}:{args.src_region} to {args.dst_cloud}:{args.dst_region} ...',
          file=sys.stderr)
    paths = []
    for i in range(len(src_ips)):
        src_ip = src_ips[i]
        print(f'Running dijkstra on src IP {src_ip} ({i}/{len(src_ips)}) ...', file=sys.stderr)
        path = graph.dijkstra(src_ip, set(dst_ips))
        if path:
            paths.append(path)
            print(path, flush=True)
        else:
            print(f'Cannot find path for src ip {src_ip}', file=sys.stderr)
    print(f'Dijkstra completed. Found {len(paths)} paths in total.', file=sys.stderr)

if __name__ == '__main__':
    main()
