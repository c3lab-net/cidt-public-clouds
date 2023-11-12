#!/usr/bin/env python3

import ast
import json
import argparse
import logging

from common import MATCHED_NODES_FILENAME_AWS, MATCHED_NODES_FILENAME_GCLOUD, init_logging

def parse_args():
    parser = argparse.ArgumentParser(description="Split JSON data by region into specified number of parts.")
    parser.add_argument('-c', '--cloud', required=True, choices=[ 'aws', 'gcloud' ], help='The cloud provider to use')
    parser.add_argument("--region", help="Region name to split", required=True)
    parser.add_argument("--parts", type=int, choices=range(1, 10), help="Number of parts to split into", required=True)
    return parser.parse_args()

def load_matched_nodes_json(filename: str) -> dict:
    logging.info(f"Loading matched nodes from {filename} ...")
    with open(filename, 'r') as f:
        data = ast.literal_eval(f.read())
    return data

def split_region_into_parts(data: dict, region: str, num_parts: int) -> dict:
    """Split a region's data into multiple parts and return a new dictionary containing them."""
    if region not in data:
        raise ValueError((f"Region '{region}' not found in the JSON file."))

    # Extract and split the region data
    logging.info(f"Splitting region '{region}' into {num_parts} parts ...")
    pairs = list(data[region].items())
    logging.info(f"Region '{region}' has {len(pairs)} pairs.")

    # Splice all pairs into multiple parts
    newdata = {}
    for i in range(num_parts):
        partial_region = f"{region}.part{i + 1}"
        partial_region_data = dict(pairs[i::num_parts])
        newdata[partial_region] = partial_region_data
        logging.info(f"Splitted '{region}' into {partial_region} with {len(partial_region_data)} pairs.")

    logging.info('Verifying splitted data ...')
    assert data[region] == { k: v for d in newdata.values() for k, v in d.items() }, "Data mismatch!"
    logging.info('Splitted data verified.')

    return newdata

def main():
    init_logging()
    args = parse_args()
    if args.cloud == 'aws':
        filename = MATCHED_NODES_FILENAME_AWS
    elif args.cloud == 'gcloud':
        filename = MATCHED_NODES_FILENAME_GCLOUD
    else:
        raise ValueError(f'Unsupported cloud {args.cloud}')

    data = load_matched_nodes_json(filename)
    newdata = split_region_into_parts(data, args.region, args.parts)
    print(data | newdata)

if __name__ == '__main__':
    main()
