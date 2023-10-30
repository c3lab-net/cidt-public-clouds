#!/usr/bin/env python3

import ast
import json
import sys
import time
import logging

CARBON_API_URL = 'http://yak-03.sysnet.ucsd.edu'

def init_logging(level=logging.DEBUG):
    logging.basicConfig(level=level,
                        stream=sys.stderr,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

def load_aws_ip_ranges(region):
    # Load the JSON data from the file
    with open('../data/cloud/ip-ranges.aws.json', 'r') as file:
        data = json.load(file)
    # Iterate through the prefixes and populate the mapping
    ip_ranges = []
    for item in data['prefixes']:
        if region and item['region'] != region:
            continue
        ip_prefix = item['ip_prefix']
        ip_ranges.append((ip_prefix, 'aws', item['region']))
    return ip_ranges

def load_gcloud_ip_ranges(region):
    with open('../data/cloud/ip-ranges.gcloud.json', 'r') as file:
        data = json.load(file)
    # Iterate through the prefixes and populate the mapping
    ip_ranges = []
    for item in data['prefixes']:
        if region and item['region'] != region:
            continue
        if 'ipv4Prefix' not in item:
            continue
        ip_prefix = item['ipv4Prefix']
        ip_ranges.append((ip_prefix, 'gcloud', item['scope']))
    return ip_ranges

def load_cloud_ip_ranges(cloud, region):
    if cloud == 'aws':
        return load_aws_ip_ranges(region)
    if cloud == 'gcloud':
        return load_gcloud_ip_ranges(region)
    raise ValueError(f'Unsupported cloud {cloud}')

def load_itdk_mapping_internal(node_file, reverse=False) -> dict:
    logging.info('Loading ITDK nodes ...')
    start_time = time.time()
    mapping_id_to_ips = {}
    mapping_ip_to_id = {}
    node_count = 0
    with open(node_file, 'r') as file:
        for line in file:
            if line.startswith('#'):
                continue

            if not line.startswith('node N'):
                logging.error('Cannot process line:', line)
                continue

            arr = line.split(':', 1)
            node_id = arr[0].split()[1]
            ips = arr[1].split()
            if reverse:
                for ip in ips:
                    mapping_ip_to_id[ip] = node_id
            else:
                mapping_id_to_ips[node_id] = ips

            node_count += 1
            if node_count % 1000000 == 0:
                elapsed_time = time.time() - start_time
                logging.debug(f'Elapsed: {elapsed_time:.2f}s, node count: {node_count}')
                # break   # _debug_
    elapsed_time = time.time() - start_time
    logging.info(f'Elapsed: {elapsed_time:.2f}s, total node count: {node_count}')
    if reverse:
        return mapping_ip_to_id
    else:
        return mapping_id_to_ips

def load_itdk_node_id_to_ips_mapping(node_file='../data/caida-itdk/midar-iff.nodes') -> dict[str, list]:
    return load_itdk_mapping_internal(node_file, False)

def load_itdk_node_ip_to_id_mapping(node_file='../data/caida-itdk/midar-iff.nodes') -> dict[str, list]:
    return load_itdk_mapping_internal(node_file, True)

def get_routes_from_file(filename) -> list[list]:
    # Read the file and count the number of entries on each line
    with open(filename, 'r') as file:
        lines = file.readlines()
        return [ ast.literal_eval(line) for line in lines ]
