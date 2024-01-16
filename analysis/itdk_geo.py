#!/usr/bin/env python3

from abc import ABC, abstractmethod
import argparse
import csv
import functools
import io
import logging
import os
import sys
import traceback
from typing import Callable, Optional
import numpy as np
import pandas as pd

from common import Coordinate, RouteInCoordinate, RouteInIP, calculate_total_distance_km, detect_cloud_regions_from_filename, get_routes_from_file, init_logging, load_itdk_node_ip_to_id_mapping, remove_duplicate_consecutive_hops
from carbon_client import get_carbon_region_from_coordinate

def parse_node_geo_as_dataframe(node_geo_filename='../data/caida-itdk/midar-iff.nodes.geo') -> pd.DataFrame:
    logging.info(f'Loading node geo entries from {node_geo_filename} ...')
    columns = ['node_id', 'continent', 'country', 'region', 'city', 'lat', 'long', 'pop', 'IX', 'source']
    column_dtypes = {
        # 'node_id': None,  # type is already specified by the converter
        'continent': str,
        'country': str,
        'region': str,
        'city': str,
        'lat': float,
        'long': float,
        'pop': str,
        'IX': str,
        'source': str,
    }
    usecols = ['node_id', 'continent', 'country', 'region', 'city', 'lat', 'long']
    converter_node_id = lambda s: s.removeprefix('node.geo ').removesuffix(':')

    node_geo_df = pd.read_csv(node_geo_filename, sep='\t', comment='#', index_col='node_id',
                              names=columns, dtype=column_dtypes, usecols=usecols,
                              converters={ 'node_id': converter_node_id }, keep_default_na=False)
    assert not node_geo_df.index.has_duplicates, f'node.geo dataframe has duplicate index on node id! ' \
            f'Count = {np.count_nonzero(node_geo_df.index.duplicated())}'
    logging.info(f'Loaded {len(node_geo_df)} entries from {node_geo_filename}.')
    return node_geo_df

def get_node_ids_with_geo_coordinates() -> list[str]:
    node_geo_df = parse_node_geo_as_dataframe()
    return node_geo_df.index.tolist()

class IpToGeoConverter(ABC):
    class LowGeoPrecisionException(Exception):
        pass

    class IpNotFoundException(Exception):
        pass

    @abstractmethod
    def convert(self, ip: str) -> Coordinate:
        pass

class MaxmindIpToGeoConverter(IpToGeoConverter):
    def __init__(self, db_path: str, accuracy_radius_threshold: float) -> None:
        """Initialize a maxmind database for ip-to-geo conversion,
            with valid conversion capped at the given accuracy radius threshold."""
        logging.info(f'Using maxmind {db_path} for ip-to-geo conversion '
                     f'(max accuracy radius = {accuracy_radius_threshold}) ...')
        import geoip2.database
        self.reader = geoip2.database.Reader(db_path)
        self.accuracy_radius_threshold = accuracy_radius_threshold

    def __del__(self):
        self.reader.close()

    def convert(self, ip: str) -> Coordinate:
        try:
            city = self.reader.city(ip)
        except Exception as ex:
            logging.warning(f'Failed to find city with ip={ip}: {ex}')
            raise IpToGeoConverter.IpNotFoundException()
        location = city.location
        if location.latitude is None or location.longitude is None:
            logging.warning(f'Location of {ip} does not have latitude or longitude')
            raise IpToGeoConverter.IpNotFoundException()
        coordinate = (location.latitude, location.longitude)
        if not location.accuracy_radius or location.accuracy_radius > self.accuracy_radius_threshold:
            logging.debug(f'Location {coordinate} has high accuracy radius of {location.accuracy_radius}')
            raise IpToGeoConverter.LowGeoPrecisionException()
        return coordinate

class ItdkIpToGeoConverter(IpToGeoConverter):
    def __init__(self) -> None:
        logging.info('Using ITDK nodes and geo dataset for ip-to-geo conversion ...')
        self.node_ip_to_id = load_itdk_node_ip_to_id_mapping()
        self.node_geo_df = parse_node_geo_as_dataframe()
        self.d_no_city_coordinates_to_node_ids: dict[Coordinate, list[str]] = {}

    def convert(self, ip: str) -> Coordinate:
        node_id = self.node_ip_to_id.get(ip, '')
        if not node_id:
            logging.warning(f'Ignoring unknown node with ip {ip}')
            raise IpToGeoConverter.IpNotFoundException()
        if node_id not in self.node_geo_df.index:
            logging.error(f'Node ID {node_id} not found in node_geo_df')
            raise IpToGeoConverter.IpNotFoundException()
        row = self.node_geo_df.loc[node_id]
        latitude = row['lat']
        longitude = row['long']
        coordinate = (latitude, longitude)
        if not row['city']:
            if coordinate not in self.d_no_city_coordinates_to_node_ids:
                self.d_no_city_coordinates_to_node_ids[coordinate] = []
            self.d_no_city_coordinates_to_node_ids[coordinate].append(node_id)
            # Note: disabled this for ITDK dataset as baseline
            # # Temporary measure to ignore intermediate hop that likely has large accuracy radius
            # #   These are known coordinates without city info and leads to problems.
            # LOW_PRECISION_COORDINATES = [
            #     (37.751, -97.822),
            #     (59.3247, 18.056),
            # ]
            # if coordinate in LOW_PRECISION_COORDINATES:
            #     raise IpToGeoConverter.LowGeoPrecisionException()
        return coordinate

def convert_routes_from_ip_to_latlon(routes: list[RouteInIP],
                                     ip_to_geo: IpToGeoConverter,
                                     is_valid_route: Callable[[RouteInCoordinate], bool],
                                     should_remove_duplicate_consecutive_hops: bool,
                                     output_file: Optional[str]) -> list[RouteInCoordinate]:
    logging.info('Converting valid routes from IPs to lat/lons ...')
    converted_routes: list[RouteInCoordinate] = []

    if output_file:
        output = open(output_file, 'w')
        logging.info(f'Writing (lat, lon) routes to {output_file} ...')
    else:
        output = None

    src_locations = set()
    dst_locations = set()

    for ip_addresses in routes:
        # Convert node IDs to latitude and longitude using the node_geo_df dictionary
        coordinates: list[Coordinate] = []
        for i in range(len(ip_addresses)):
            ip_address = ip_addresses[i]
            try:
                coordinate = ip_to_geo.convert(ip_address)
            except IpToGeoConverter.IpNotFoundException:
                logging.warning(f'IP {ip_address} not found, ignoring route!')
                break
            except IpToGeoConverter.LowGeoPrecisionException:
                logging.warning(f'IP {ip_address} has low-precision coordinate, ignoring route!')
                break
            coordinates.append(coordinate)

        # If some nodes failed to convert, we ignore the route
        if len(coordinates) < len(ip_addresses):
            continue

        # Route must have at least 2 hops, at src and dst.
        if len(coordinates) < 2:
            logging.warning(f'Ignoring route with less than 2 hops: {coordinates}')
            continue

        src_locations.add(coordinates[0])
        dst_locations.add(coordinates[-1])

        # Check if the route is valid
        if not is_valid_route(coordinates):
            continue

        if should_remove_duplicate_consecutive_hops:
            remove_duplicate_consecutive_hops(coordinates)

        # Append the converted route to the result
        print(coordinates, file=output if output else sys.stdout)
        converted_routes.append(coordinates)

    if output:
        output.close()

    logging.info('Source locations (%d):', len(src_locations))
    for coordinate in src_locations:
        logging.info(f'{coordinate} ({get_carbon_region_from_coordinate(coordinate)})')
    logging.info('Destination locations (%d):', len(dst_locations))
    for coordinate in dst_locations:
        logging.info(f'{coordinate} ({get_carbon_region_from_coordinate(coordinate)})')

    logging.info('Converted/Total: %d/%d', len(converted_routes), len(routes))

    if isinstance(ip_to_geo, ItdkIpToGeoConverter):
        logging.info('Empty city coordinates:')
        for coordinate, node_ids in ip_to_geo.d_no_city_coordinates_to_node_ids.items():
            logging.info(f'{coordinate} ({len(node_ids)}): {" ".join(node_ids)}')

    return converted_routes

def load_region_to_geo_coordinate_ground_truth(geo_coordinate_ground_truth_csv: io.TextIOWrapper) -> \
                                                dict[str, Coordinate]:
    with geo_coordinate_ground_truth_csv as f:
        csv_reader = csv.DictReader(f)
        d_region_to_coordinate: dict[str, Coordinate] = {}
        for row in csv_reader:
            region_key = f"{row['cloud']}:{row['region']}"
            coordinates = (float(row['latitude']), float(row['longitude']))
            d_region_to_coordinate[region_key] = coordinates
    return d_region_to_coordinate

def get_route_check_function_by_ground_truth(geo_coordinate_ground_truth: dict[str, Coordinate],
                                             src_cloud: str, src_region: str,
                                             dst_cloud: str, dst_region: str) -> \
                                                Callable[[RouteInCoordinate], bool]:
        src = f'{src_cloud}:{src_region}'
        dst = f'{dst_cloud}:{dst_region}'
        try:
            src_coordinate = geo_coordinate_ground_truth[src]
            dst_coordinate = geo_coordinate_ground_truth[dst]
            src_iso = get_carbon_region_from_coordinate(src_coordinate)
            dst_iso = get_carbon_region_from_coordinate(dst_coordinate)
        except KeyError as ex:
            logging.error(f'KeyError: {ex}')
            logging.error(traceback.format_exc())
            raise ValueError(f'Region not found in ground truth CSV: {ex}')

        logging.info('Filtering routes based on ground truth geo coordinates of src and dst, converted to ISOs ...')
        logging.info(f'Ground truth: src: {src} -> {src_coordinate} ({src_iso}), '
                     f'dst: {dst} -> {dst_coordinate} ({dst_iso})')
        # Allow small inaccuracy for certain US regions' ISO mapping.
        ISO_MISMATCH_WHITELIST = [
            ('emap:US-TEN-TVA', 'emap:US-SE-SOCO'),
            ('emap:US-CENT-SWPP', 'emap:US-MIDW-AECI'),
            ('emap:US-CAR-SC', 'emap:US-CAR-SCEG'),
            ('emap:US-NW-SCL', 'emap:US-NW-PACW'),
        ]
        ISO_MISMATCH_DISTANCE_THRESHOLD_KM = 250
        @functools.cache
        def are_isos_equal(coord1: Coordinate, coord2: Coordinate):
            iso1 = get_carbon_region_from_coordinate(coord1)
            logging.debug(f'ISO mapping: {coord1} -> {iso1}')
            iso2 = get_carbon_region_from_coordinate(coord2)
            distance_km = calculate_total_distance_km([coord1, coord2])
            if iso1 == iso2:
                return True
            elif (iso1, iso2) in ISO_MISMATCH_WHITELIST and distance_km < ISO_MISMATCH_DISTANCE_THRESHOLD_KM:
                logging.info(f'ISO mismatch allowed: {coord1} ({iso1}) != {coord2} ({iso2}). Distance: {distance_km:.2f}km')
                return True
            else:
                logging.info(f'ISO mismatch disallowed: {coord1} ({iso1}) != {coord2} ({iso2}). Distance: {distance_km:.2f}km')
                return False

        check_route_by_ground_truth = lambda route: are_isos_equal(route[0], src_coordinate) and are_isos_equal(route[-1], dst_coordinate)
        return check_route_by_ground_truth

def generate_direct_route_from_ground_truth(geo_coordinate_ground_truth: dict[str, Coordinate],
                                             src_cloud: str, src_region: str,
                                             dst_cloud: str, dst_region: str) -> \
                                                list[RouteInCoordinate]:
    src = f'{src_cloud}:{src_region}'
    dst = f'{dst_cloud}:{dst_region}'
    try:
        src_coordinate = geo_coordinate_ground_truth[src]
        dst_coordinate = geo_coordinate_ground_truth[dst]
        route = [src_coordinate, dst_coordinate]
        return [route]
    except KeyError as ex:
        logging.error(f'KeyError: {ex}')
        logging.error(traceback.format_exc())
        raise ValueError(f'Region not found in ground truth CSV: {ex}')

def write_routes_to_file(routes: list[RouteInCoordinate], output_file: Optional[str]):
    if output_file:
        output = open(output_file, 'w')
        logging.info(f'Writing (lat, lon) routes to {output_file} ...')
    else:
        output = sys.stdout

    for route in routes:
        print(route, file=output)

    if output_file:
        output.close()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_files', type=str, required=True, nargs='+', help='The routes file, each line contains a list that represents a route.')
    parser.add_argument('--convert-ip-to-latlon', action='store_true',
                        help='Convert the routes from IP addresses to lat/lon coordinates')
    parser.add_argument('--generate-direct-route-using-ground-truth', action='store_true', help='Generate direct route between cloud region pairs using ground truth src and dst geo coordinates.')
    parser.add_argument('-o', '--outputs', type=str, nargs='*', help='The output file.')
    parser.add_argument('--filter-geo-coordinate-by-ground-truth', action='store_true',
                        help='Filter the routes by ground truth geo coordinates.')
    parser.add_argument('--geo-coordinate-ground-truth-csv', type=argparse.FileType('r'),
                        help='The CSV file containing the ground truth geo coordinates.')
    parser.add_argument('--remove-duplicate-consecutive-hops', action='store_true',
                        help='Remove duplicate consecutive hops from the routes.')
    parser.add_argument('--src-cloud', required=False, help='The source cloud')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud')
    parser.add_argument('--src-region', required=False, help='The source region')
    parser.add_argument('--dst-region', required=False, help='The destination region')
    parser.add_argument('--maxmind-database', type=str, help='Path to maxmind database to read directly')
    parser.add_argument('--accuracy-radius-threshold', type=float, help='Maximum accuracy redius to accept a coordinate')

    args = parser.parse_args()

    if args.outputs is not None and len(args.outputs) not in [0, len(args.routes_files)]:
        parser.error('The number of output files must match the number of routes files, or be 0 (auto-naming files)')

    if args.filter_geo_coordinate_by_ground_truth:
        if not args.geo_coordinate_ground_truth_csv:
            parser.error('--geo-coordinate-ground-truth-csv must be specified when --filter-geo-coordinate-by-ground-truth is specified')

    if args.generate_direct_route_using_ground_truth:
        if not args.geo_coordinate_ground_truth_csv:
            parser.error('--geo-coordinate-ground-truth-csv must be specified when '
                         '--generate-direct-route-using-ground-truth is specified')

    if args.geo_coordinate_ground_truth_csv:
        args.cloud_region_pair_by_filename = {}
        if not args.src_cloud and not args.dst_cloud and not args.src_region and not args.dst_region:
            # Check if we can auto-detect the src and dst cloud/region from the routes files
            for routes_file in args.routes_files:
                cloud_regions = detect_cloud_regions_from_filename(routes_file)
                if cloud_regions is None:
                    parser.error('Cannot auto-detect cloud regions from the filename "%s"' % routes_file)
                else:
                    logging.info(f'Auto-detected cloud regions from filename "{routes_file}": {cloud_regions}')
                    args.cloud_region_pair_by_filename[routes_file] = cloud_regions
        else:
            if not args.src_cloud:
                parser.error('--src-cloud must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.dst_cloud:
                parser.error('--dst-cloud must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.src_region:
                parser.error('--src-region must be specified when --filter-geo-coordinate-by-ground-truth is specified')
            if not args.dst_region:
                parser.error('--dst-region must be specified when --filter-geo-coordinate-by-ground-truth is specified')

    if args.maxmind_database:
        if not os.path.exists(args.maxmind_database):
            parser.error(f'Maxmind database {args.maxmind_database} not found!')
        if not args.accuracy_radius_threshold:
            parser.error('--accuracy-radius-threshold must be specified when --maxmind-database is sepcified')

    if args.accuracy_radius_threshold and not args.maxmind_database:
        parser.error('--maxmind-database must be specified when --accuracy-radius-threshold is sepcified')

    return args

def get_src_dst_cloud_region(routes_file: str, args) -> tuple[str, str, str, str]:
    if routes_file in args.cloud_region_pair_by_filename:
        (src_cloud, src_region, dst_cloud, dst_region) = args.cloud_region_pair_by_filename[routes_file]
    else:
        (src_cloud, src_region) = (args.src_cloud, args.src_region)
        (dst_cloud, dst_region) = (args.dst_cloud, args.dst_region)
    return (src_cloud, src_region, dst_cloud, dst_region)

def generate_output_filename(routes_file: str, outputs, i) -> Optional[str]:
    if outputs is not None:
        if len(outputs) == 0:
            output_file = os.path.basename(routes_file).removesuffix('.by_ip') + '.by_geo'
        else:
            output_file = outputs[i]
    else:
        output_file = None
    return output_file

def main():
    init_logging(level=logging.INFO)
    args = parse_args()
    if args.convert_ip_to_latlon:
        if args.maxmind_database:
            ip_to_geo_converter = MaxmindIpToGeoConverter(args.maxmind_database, args.accuracy_radius_threshold)
        else:
            ip_to_geo_converter = ItdkIpToGeoConverter()
        geo_coordinate_ground_truth = \
            load_region_to_geo_coordinate_ground_truth(args.geo_coordinate_ground_truth_csv) \
            if args.filter_geo_coordinate_by_ground_truth else {}
        for i in range(len(args.routes_files)):
            routes_file: str = args.routes_files[i]
            output_file = generate_output_filename(routes_file, args.outputs, i)
            # Generate check route function
            if args.filter_geo_coordinate_by_ground_truth:
                check_route_by_ground_truth = \
                    get_route_check_function_by_ground_truth(geo_coordinate_ground_truth,
                                                            *get_src_dst_cloud_region(routes_file, args))
            else:
                check_route_by_ground_truth = lambda _: True
            # Convert routes
            logging.info(f'Converting routes from {routes_file} to {output_file if output_file else "stdout"} ...')
            routes = get_routes_from_file(routes_file)
            convert_routes_from_ip_to_latlon(routes, ip_to_geo_converter,
                                             check_route_by_ground_truth,
                                             args.remove_duplicate_consecutive_hops,
                                             output_file)
    elif args.generate_direct_route_using_ground_truth:
        geo_coordinate_ground_truth = load_region_to_geo_coordinate_ground_truth(args.geo_coordinate_ground_truth_csv)
        for i in range(len(args.routes_files)):
            routes_file: str = args.routes_files[i]
            output_file = generate_output_filename(routes_file, args.outputs, i)
            routes = generate_direct_route_from_ground_truth(geo_coordinate_ground_truth,
                                                            *get_src_dst_cloud_region(routes_file, args))
            write_routes_to_file(routes, output_file)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()

