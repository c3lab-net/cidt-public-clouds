#!/usr/bin/env python3


import ast
import logging
import time
import argparse
# from ipaddress import IPv4Address, IPv4Network
from cidr_trie import PatriciaTrie

from common import init_logging, load_cloud_ip_ranges, load_itdk_node_id_to_ips_mapping

def build_trie_from_ip_ranges(ip_ranges: list[tuple]) -> PatriciaTrie:
    trie = PatriciaTrie()
    for ip_range in ip_ranges:
        trie.insert(ip_range[0], (ip_range[1:]))
    logging.info(f'Built trie with {trie.size}')
    return trie

def get_matching_ips(ips: list[str], cidr_trie: PatriciaTrie) -> list[tuple]:
    matching_ips = []
    for ip in ips:
        if ip.count('.') != 3:
            logging.error(f'Invalid IP: {ip}')
            continue
        matching_ips += [(ip,) + t for t in cidr_trie.find_all(ip)]
    return matching_ips

def get_matching_node_ips(cidr_trie: PatriciaTrie, itdk_node_id_to_ips: dict[str, list]):
    logging.info('Starting to match nodes in ITDK nodes ...')
    matched_node_ips = {}
    node_count = 0
    ip_count = 0
    start_time = time.time()
    for node_id, ips in itdk_node_id_to_ips.items():
        matched_ips = get_matching_ips(ips, cidr_trie)
        if matched_ips:
            matched_node_ips[node_id] = matched_ips

        node_count += 1
        ip_count += len(ips)
        if node_count % 1000000 == 0:
            elapsed_time = time.time() - start_time
            logging.debug(f'Elapsed: {elapsed_time:.2f}s, node processed: {node_count}, ip count: {ip_count}')
            matched_ip_count = sum([len(v) for _, v in matched_node_ips.items()])
            logging.debug(f'Matched IPs: {matched_ip_count}')

    return matched_node_ips

def convert_matched_nodes_to_by_region(matched_nodes_file, ip_ranges):
    # by region, node, prefix then ip.
    logging.info('Converting matched nodes format ...')
    with open(matched_nodes_file) as file:
        dict_str = file.read()
        d_by_node = ast.literal_eval(dict_str)
    d_by_region = {}
    for node_id in d_by_node:
        for (ip, prefix, data) in d_by_node[node_id]:
            region = data[1] if data else next(e[2] for e in ip_ranges if e[0] == prefix)
            if region not in d_by_region:
                d_by_region[region] = {}
            if node_id not in d_by_region[region]:
                d_by_region[region][node_id] = []
            d_by_region[region][node_id].append((prefix, ip))
    return d_by_region

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cloud', required=True, choices=[ 'aws', 'gcloud' ], help='The cloud provider to use')
    parser.add_argument('-r', '--region', required=False, help='The region to match')
    parser.add_argument('--convert_to_by_region', action='store_true', help='Convert the result to be by region')
    parser.add_argument('--match_cloud_ips_with_itdk', action='store_true', help='Match nodes in the ITDK dataset')
    parser.add_argument('--matched_nodes_file', help='The matched nodes dictionary file, keyed by node id')
    args = parser.parse_args()

    if args.convert_to_by_region:
        if not args.matched_nodes_file:
            parser.error('--convert_to_by_region requires --matched_nodes_file')
    elif args.match_cloud_ips_with_itdk:
        pass
    else:
        parser.error('No action specified')

    return args

def main():
    init_logging()
    args = parse_args()
    ip_ranges = load_cloud_ip_ranges(args.cloud, args.region)

    logging.info(f'Cloud: {args.cloud}, region: {args.region}')
    logging.info('IP ranges:')
    for ip_range in ip_ranges:
        logging.info(ip_range)

    if args.convert_to_by_region:
        matched_nodes_to_by_region = convert_matched_nodes_to_by_region(args.matched_nodes_file, ip_ranges)
        print(matched_nodes_to_by_region)
    elif args.match_cloud_ips_with_itdk:
        trie = build_trie_from_ip_ranges(ip_ranges)
        itdk_node_id_to_ips = load_itdk_node_id_to_ips_mapping()
        matching_node_and_ips = get_matching_node_ips(trie, itdk_node_id_to_ips)
        print(matching_node_and_ips)

if __name__ == '__main__':
    main()
