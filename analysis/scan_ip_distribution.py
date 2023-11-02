#!/usr/bin/env python3

import logging
import sys
from ipaddress import IPv4Network, IPv4Address

from common import init_logging

def build_prefix_set(prefix_file):
    prefix_set = set()
    with open(prefix_file, 'r') as f:
        for line in f:
            prefix = line.strip()
            prefix_set.add(IPv4Network(prefix, strict=False))
    return prefix_set

def match_ip_addresses(ip_file, prefix_set):
    prefix_distribution = {}

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
            else:
                logging.error(f"IP {ip} does not match any prefix")

    print("\nDistribution of matched prefixes:")
    for prefix, count in prefix_distribution.items():
        print(f"{prefix}: {count} occurrences")

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py prefix_file ip_file")
        sys.exit(1)

    init_logging(level=logging.INFO)

    prefix_file = sys.argv[1]
    ip_file = sys.argv[2]

    prefix_set = build_prefix_set(prefix_file)
    match_ip_addresses(ip_file, prefix_set)

if __name__ == "__main__":
    main()
