#!/usr/bin/env python3

import argparse
from collections import Counter
import logging

import requests

from common import get_routes_from_file, CARBON_API_URL, init_logging

def get_carbon_region_from_coordinate(coordinate: tuple[float, float]):
    (latitude, longitude) = coordinate
    response = requests.get(f'{CARBON_API_URL}/balancing-authority/', params={
        'latitude': latitude,
        'longitude': longitude,
        'iso_format': 'emap',
    })
    try:
        assert response.ok, "Carbon region lookup failed for %s (%d): %s" % (coordinate, response.status_code, response.text)
        response_json = response.json()
        return response_json['iso']
    except Exception as ex:
        logging.error(ex)
        return 'Unknown'

def convert_latlon_to_carbon_region(routes: list[list[tuple[float, float]]]):
    coordinates = set()
    for route in routes:
        for coordinate in route:
            coordinates.add(coordinate)

    d_coordinate_to_carbon_region = {}
    for coordinate in coordinates:
        d_coordinate_to_carbon_region[coordinate] = get_carbon_region_from_coordinate(coordinate)

    routes_in_carbon_region = []
    for route in routes:
        route_in_carbon_region = []
        for coordinate in route:
            carbon_region = d_coordinate_to_carbon_region[coordinate]
            route_in_carbon_region.append(carbon_region)
        routes_in_carbon_region.append(route_in_carbon_region)
        print(route_in_carbon_region)
    return routes_in_carbon_region

def export_routes_distribution(routes: list[list]):
    logging.info('Exporting routes distribution ...')

    routes_as_str = [ '|'.join(route) for route in routes ]
    for route_str, count in sorted(Counter(routes_as_str).items(), key=lambda x: x[1], reverse=True):
        print(count, route_str)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('--convert-latlon-to-carbon-region', action='store_true',
                        help='Convert the routes from lat/lon coordinates to Carbon region names.')
    parser.add_argument('--export-routes-distribution', action='store_true',
                        help='Export the routes distribution.')
    args = parser.parse_args()

    if (args.convert_latlon_to_carbon_region or args.export_routes_distribution) and args.routes_file is None:
        parser.error('routes_file must be specified when --convert-latlon-to-carbon-region or --export-routes-distribution is specified')

    return args

def main():
    init_logging()
    args = parse_args()
    if args.convert_latlon_to_carbon_region:
        routes = get_routes_from_file(args.routes_file)
        routes_in_carbon_region = convert_latlon_to_carbon_region(routes)
        # print(routes_in_carbon_region)
    elif args.export_routes_distribution:
        routes = get_routes_from_file(args.routes_file)
        export_routes_distribution(routes)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
