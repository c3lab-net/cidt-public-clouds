#!/usr/bin/env python3

import argparse
import logging
from ipaddress import IPv4Network, IPv4Address

from common import init_logging

def build_prefix_set(prefix_files: list[str]) -> tuple[set[IPv4Network], dict[str, str]]:
    """Build a set of prefixes from the given files, also and returns a dict that maps each prefix to its name."""
    logging.info(f'Building prefix set... from {len(prefix_files)} files ...')
    prefix_set: set[IPv4Network] = set()
    d_prefix_to_file: dict[str, str] = {}
    for prefix_file in prefix_files:
        logging.info(f'Adding prefixes from {prefix_file} ...')
        file_prefix_count = 0
        with open(prefix_file, 'r') as f:
            for line in f:
                prefix = line.strip()
                prefix_set.add(IPv4Network(prefix, strict=False))
                d_prefix_to_file[prefix] = prefix_file
                file_prefix_count += 1
        logging.info(f'Added {file_prefix_count} prefixes from {prefix_file} ...')
    logging.info(f'Added {len(prefix_set)} prefixes from {len(prefix_files)} files ...')
    return prefix_set, d_prefix_to_file

def match_ip_addresses(ip_file: str, prefix_set: set[IPv4Network], d_prefix_to_file: dict[str, str],
                       show_matched_ips: bool):
    prefix_distribution = {}
    d_file_matched_prefixes = {}
    prefix_to_ips = {}

    logging.info(f'Matching IP addresses from {ip_file} ...')

    with open(ip_file, 'r') as f:
        for line in f:
            ip = line.strip()
            if not ip:
                continue
            ip_address = IPv4Address(ip)
            matched_prefix = None
            for prefix in prefix_set:
                if ip_address in prefix:
                    matched_prefix = str(prefix)
                    break

            if matched_prefix:
                logging.debug(f"IP {ip} matches prefix {matched_prefix}")
                prefix_distribution[matched_prefix] = prefix_distribution.get(matched_prefix, 0) + 1
                d_file_matched_prefixes.setdefault(d_prefix_to_file[matched_prefix], set()).add(matched_prefix)
                prefix_to_ips.setdefault(matched_prefix, []).append(ip)
            else:
                logging.error(f"IP {ip} does not match any prefix")

    print("\nDistribution of matched prefixes:")
    for file, matched_prefixes in d_file_matched_prefixes.items():
        print(f"{file}:")
        total_matched_ips = 0
        for prefix, count in prefix_distribution.items():
            if prefix not in matched_prefixes:
                continue
            total_matched_ips += count
            if show_matched_ips:
                print(f"\t{prefix}: {count} occurrences: {prefix_to_ips[prefix]}")
            else:
                print(f"\t{prefix}: {count} occurrences")
        print(f"Total: {len(matched_prefixes)} prefixes, {total_matched_ips} matched IPs\n")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('ip_file', type=str,
                        help='The file that contains the IP addresses to match')
    parser.add_argument('prefix_files', type=str, nargs='+',
                        help='The IP prefix files, each line contains one CIDR ranges.')
    parser.add_argument('-s', '--show-matched-ips', action='store_true',
                        help='Show the matched IP addresses')
    args = parser.parse_args()

    return args

def main():
    init_logging(level=logging.INFO)

    args = parse_args()

    prefix_set, d_prefix_to_file = build_prefix_set(args.prefix_files)
    match_ip_addresses(args.ip_file, prefix_set, d_prefix_to_file, args.show_matched_ips)

if __name__ == "__main__":
    main()
