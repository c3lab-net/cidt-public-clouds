#!/usr/bin/env python3

import argparse
import io
import logging
import sys
import traceback
from typing import Optional
import requests_cache

from common import get_routes_from_file, init_logging

Coordinate=tuple[float, float]
Route=list[Coordinate]

session = requests_cache.CachedSession('igdb_cache', backend='filesystem')
IGDB_API_URL = 'http://localhost:8082'

def get_igdb_physical_hops(src: Coordinate, dst: Coordinate) -> Route:
    """Get the physical hops between two coordinates using iGDB."""
    (src_lat, src_lon) = src
    (dst_lat, dst_lon) = dst
    response = session.get(f'{IGDB_API_URL}/physical-route/', params={
        'src_latitude': src_lat,
        'src_longitude': src_lon,
        'dst_latitude': dst_lat,
        'dst_longitude': dst_lon,
    })
    try:
        assert response.ok, "iGDB physical hops lookup failed for %s -> %s (%d): %s" % \
            (src, dst, response.status_code, response.text)
        response_json = response.json()
        assert isinstance(response_json, list), 'Invalid iGDB physical hops lookup response: %s' % response.text
        assert len(response_json) >= 2, 'Expect at least two hops in the physical route, but got %s' % response.text
    except Exception as ex:
        logging.error(ex)
        logging.error(traceback.format_exc())
        raise

    physical_hops = []
    for hop in response_json:
        # Convert JSON list to python tuple
        physical_hops.append(tuple(hop))
    return physical_hops

def convert_logical_route_to_physical_route(route: Route) -> Route:
    physical_route: Route = []
    for i in range(len(route) - 1):
        hop1 = route[i]
        hop2 = route[i + 1]
        # Each logical step can have multiple physical hops
        intermediate_hops = get_igdb_physical_hops(hop1, hop2)
        # Remove the first hop if it is the same as the last hop of the previous step
        if len(physical_route) > 0 and intermediate_hops[0] == physical_route[-1]:
            intermediate_hops = intermediate_hops[1:]
        physical_route += intermediate_hops[:-1]
    return physical_route

def convert_all_logical_routes_to_physical_routes(logical_routes: list[Route],
                                                  output: Optional[io.TextIOWrapper]) -> None:
    for route in logical_routes:
        physical_route = convert_logical_route_to_physical_route(route)
        print(physical_route, file=output if output else sys.stdout)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The logical routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='The output file.')
    parser.add_argument('--convert-to-physical-hops', action='store_true',
                        help='Convert the routes from logical hops to physical hops using iGDB dataset.')
    args = parser.parse_args()

    if not args.convert_to_physical_hops:
        parser.error('No action requested.')

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()
    if args.convert_to_physical_hops:
        logical_routes = get_routes_from_file(args.routes_file)
        convert_all_logical_routes_to_physical_routes(logical_routes, args.output)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
