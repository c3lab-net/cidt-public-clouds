#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
import functools
import io
import logging
import math
import sys
import traceback
from typing import Optional
import requests_cache
from shapely import wkt
from shapely.geometry import MultiLineString
from geopy.distance import geodesic, lonlat, great_circle

from common import detect_cloud_regions_from_filename, get_routes_from_file, init_logging

Coordinate=tuple[float, float]
LogicalRoute=list[Coordinate]

@dataclass
class PhysicalRoute:
    routers_latlon: list[Coordinate]
    distance_km: float
    fiber_wkt_paths: MultiLineString
    fiber_types: list[str]

    def validate(self):
        assert isinstance(self.routers_latlon, list) and len(self.routers_latlon) >= 2, \
            'Expect at least two hops in the physical route, but got %s' % self.routers_latlon
        assert self.distance_km >= 0, 'Expect distance_km >= 0, but got %s' % self.distance_km
        assert self.fiber_wkt_paths.geom_type == 'MultiLineString', \
                'Expect fiber_wkt_paths to be a MultiLineString, but got %s' % self.fiber_wkt_paths.geom_type
        assert len(self.fiber_wkt_paths.geoms) == len(self.routers_latlon) - 1, \
                'Expect fiber_wkt_paths to have %d lines, but got %d' % \
                    (len(self.routers_latlon) - 1, len(self.fiber_wkt_paths.geoms))
        assert len(self.fiber_types) == len(self.fiber_wkt_paths.geoms), \
                'Expect fiber_types to have %d elements, but got %d' % \
                    (len(self.fiber_wkt_paths.geoms), len(self.fiber_types))
        for fiber_type in self.fiber_types:
            assert fiber_type in ['land', 'submarine'], 'Invalid fiber_type %s' % fiber_type

    def extend(self, other):
        if not isinstance(other, PhysicalRoute):
            raise ValueError('Expect other to be a PhysicalRoute, but got %s' % other)
        if len(self.routers_latlon) == 0:
            self.routers_latlon.extend(other.routers_latlon)
            self.distance_km = other.distance_km
            self.fiber_wkt_paths = MultiLineString(other.fiber_wkt_paths.geoms)
            self.fiber_types = list(other.fiber_types)
            return
        # Connect physical hops together, while removing the common intermediate router hop
        THRESHOLD_CONSECUTIVE_HOPS_KM = 5
        assert geodesic(self.routers_latlon[-1], other.routers_latlon[0]).km < THRESHOLD_CONSECUTIVE_HOPS_KM, \
            'Expect the last hop in self to be the same as the first hop in other, but got %s and %s' % \
                (self.routers_latlon[-1], other.routers_latlon[0])
        # intermediate hops can get a redirect router hop, i.e. this[-2] = closest city, this[-1] = logical stop,
        #   other[0] = logical stop, and other[1] = closest city = this[-2]. In that case, we need to remove the intermediate hop (last of self, and first of other), and adjust the fiber paths and distances accordingly.
        THRESHOLD_INTERMEDIATE_REDIRECT_KM = 50
        remove_direct_hop = False
        if len(self.routers_latlon) > 2 and len(other.routers_latlon) > 2 and \
                geodesic(self.routers_latlon[-2], other.routers_latlon[1]).km < THRESHOLD_INTERMEDIATE_REDIRECT_KM:
            self_extra_hop_distance_km = geodesic(
                lonlat(*self.fiber_wkt_paths.geoms[-1].coords[0]),
                lonlat(*self.fiber_wkt_paths.geoms[-1].coords[-1])).km
            other_extra_hop_distance_km = geodesic(
                lonlat(*other.fiber_wkt_paths.geoms[0].coords[0]),
                lonlat(*other.fiber_wkt_paths.geoms[0].coords[-1])).km
            if math.isclose(self_extra_hop_distance_km, other_extra_hop_distance_km,
                            abs_tol=THRESHOLD_INTERMEDIATE_REDIRECT_KM) and \
                    self_extra_hop_distance_km < THRESHOLD_INTERMEDIATE_REDIRECT_KM:
                remove_direct_hop = True
        if remove_direct_hop:
            logging.info(f'Removing extra detour stop via {self.routers_latlon[-2]} '
                         f'to {self.routers_latlon[-1]} of length {self_extra_hop_distance_km:.2f}km')
            # Remove last fiber path of self and first fiber path of other.
            self.routers_latlon = self.routers_latlon[:-1] + other.routers_latlon[2:]
            self.distance_km = (self.distance_km - self_extra_hop_distance_km) + \
                                (other.distance_km - other_extra_hop_distance_km)
            self.fiber_wkt_paths = MultiLineString(list(self.fiber_wkt_paths.geoms)[:-1] + \
                                                    list(other.fiber_wkt_paths.geoms)[1:])
            self.fiber_types = self.fiber_types[:-1] + other.fiber_types[1:]
        else:   # Normal case, discard starting hop of other
            self.routers_latlon.extend(other.routers_latlon[1:])
            self.distance_km += other.distance_km
            self.fiber_wkt_paths = MultiLineString(list(self.fiber_wkt_paths.geoms) + \
                                                    list(other.fiber_wkt_paths.geoms))
            self.fiber_types.extend(other.fiber_types)

    def to_tsv(self):
        return '\t'.join([
            str(self.routers_latlon),
            str(self.distance_km),
            self.fiber_wkt_paths.wkt,
            '|'.join(self.fiber_types),
        ])

igdb_session = None
IGDB_API_URL = 'http://localhost:8083'

def load_fiber_wkt_paths(fiber_wkt_paths: str) -> MultiLineString:
    try:
        return wkt.loads(fiber_wkt_paths)
    except Exception as ex:
        logging.error(ex)
        logging.error(traceback.format_exc())
        raise AssertionError('Invalid fiber_wkt_paths %s: %s' % (fiber_wkt_paths, ex))

def get_igdb_physical_hops(src: Coordinate, dst: Coordinate,
                           src_cloud: str, dst_cloud: str,
                           include_nearby_as_locations: bool) -> PhysicalRoute:
    """Get the physical hops between two coordinates using iGDB, inclusive of both ends."""
    (src_lat, src_lon) = src
    (dst_lat, dst_lon) = dst
    assert igdb_session is not None
    response = igdb_session.get(f'{IGDB_API_URL}/physical-route/', params={
        'src_latitude': src_lat,
        'src_longitude': src_lon,
        'dst_latitude': dst_lat,
        'dst_longitude': dst_lon,
        'src_cloud': src_cloud,
        'dst_cloud': dst_cloud,
        'search_for_nearby_as_locations': include_nearby_as_locations,
    })
    assert response.ok, "iGDB physical hops lookup failed for %s -> %s (%d): %s" % \
        (src, dst, response.status_code, response.text)
    response_json = response.json()

    routers_latlon: list[Coordinate] = [Coordinate(item) for item in response_json['routers_latlon']]
    distance_km: float = response_json['distance_km']
    fiber_wkt_paths: MultiLineString = load_fiber_wkt_paths(response_json['fiber_wkt_paths'])
    fiber_types: list[str] = response_json['fiber_types']

    physical_route = PhysicalRoute(routers_latlon, distance_km, fiber_wkt_paths, fiber_types)
    physical_route.validate()

    return physical_route

def validate_start_end_offset(logical_route: LogicalRoute, physical_route: PhysicalRoute) -> None:
    logical_start = logical_route[0]
    logical_end = logical_route[-1]
    physical_start = physical_route.routers_latlon[0]
    physical_end = physical_route.routers_latlon[-1]

    logging.info('\tlogical route: start=%s, end=%s, physical route: start=%s, end=%s',
                 logical_start, logical_end, physical_start, physical_end)

    start_offset_km = geodesic(logical_start, physical_start).km
    end_offset_km = geodesic(logical_end, physical_end).km
    DISTANCE_THRESHOLD_KM = 50
    logging.info('\tdistance (logical->physical): start = %f km, end = %f km',
                 start_offset_km, end_offset_km)
    assert start_offset_km < DISTANCE_THRESHOLD_KM, 'Start offset is too large: %f km' % start_offset_km
    assert end_offset_km < DISTANCE_THRESHOLD_KM, 'End offset is too large: %f km' % end_offset_km

def get_great_circle_distance_km(logical_route: LogicalRoute) -> float:
    return great_circle(logical_route[0], logical_route[-1]).km

@functools.cache
def convert_logical_route_to_physical_route(logical_route: LogicalRoute,
                                            src_cloud: str,
                                            dst_cloud: str,
                                            include_nearby_as_locations: bool) -> Optional[PhysicalRoute]:
    logging.info('Converting logical route %s ...', logical_route)
    physical_route: PhysicalRoute = PhysicalRoute([], 0, MultiLineString([]), [])
    for i in range(len(logical_route) - 1):
        intermediate_hops = get_igdb_physical_hops(logical_route[i], logical_route[i + 1],
                                                   src_cloud, dst_cloud,
                                                   include_nearby_as_locations)
        physical_route.extend(intermediate_hops)
    validate_start_end_offset(logical_route, physical_route)
    great_circle_distance_km = get_great_circle_distance_km(logical_route)
    if physical_route.distance_km > 2 * great_circle_distance_km:
        logging.warning('Physical route is too long: %.2f > 2 * %.2f' % \
                        (physical_route.distance_km, great_circle_distance_km))
        return None
    else:
        return physical_route

def convert_all_logical_routes_to_physical_routes(logical_routes: list[LogicalRoute],
                                                  src_cloud: str,
                                                  dst_cloud: str,
                                                  include_nearby_as_locations: bool,
                                                  output: Optional[io.TextIOWrapper]) -> None:
    for logical_route in logical_routes:
        try:
            physical_route = convert_logical_route_to_physical_route(tuple(logical_route), src_cloud, dst_cloud,
                                                                     include_nearby_as_locations)
            if physical_route:
                print(physical_route.to_tsv(), file=output if output else sys.stdout)
        except AssertionError as ex:
            logging.error(f"Ignoring failed conversion of logical route {logical_route}: {ex}")
            logging.error(traceback.format_exc())
    if output:
        output.close()

def init_igdb_api_cache(preserve_cache: bool):
    global igdb_session
    if preserve_cache:
        cache_name = 'igdb_cache'
        backend = 'filesystem'
    else:
        cache_name = 'igdb_cache.ram'
        backend='memory'
    igdb_session = requests_cache.CachedSession(cache_name, backend=backend, allowable_codes=(200, 400))

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', type=str, help='The logical routes file, each line contains a list of (lat, long) coordinates and represents a route.')
    parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='The output file.')
    parser.add_argument('--convert-to-physical-hops', action='store_true',
                        help='Convert the routes from logical hops to physical hops using iGDB dataset.')
    parser.add_argument('--src-cloud', required=False, help='The source cloud')
    parser.add_argument('--dst-cloud', required=False, help='The destination cloud')
    parser.add_argument('--include-nearby-as-locations', action='store_true',
                        help='Whether to include nearby AS locations in iGDB physical hops lookup')
    parser.add_argument('--preserve-igdb-api-cache', action='store_true',
                        help='Whether to preserve on disk the iGDB API calls')
    args = parser.parse_args()

    if not args.convert_to_physical_hops:
        parser.error('No action requested.')

    if not args.src_cloud and not args.dst_cloud:
        cloud_regions = detect_cloud_regions_from_filename(args.routes_file)
        if cloud_regions:
            (args.src_cloud, args.src_region, args.dst_cloud, args.dst_region) = cloud_regions
        else:
            parser.error('Either src_cloud or dst_cloud is required.')
    elif args.src_cloud and args.dst_cloud:
        pass
    else:
        parser.error('Both src_cloud and dst_cloud are required.')

    if args.include_nearby_as_locations:
        logging.info('Including nearby AS locations in iGDB physical hops lookup ...')

    return args

def main():
    init_logging(level=logging.INFO)
    args = parse_args()
    init_igdb_api_cache(args.preserve_igdb_api_cache)
    if args.convert_to_physical_hops:
        logical_routes = get_routes_from_file(args.routes_file)
        convert_all_logical_routes_to_physical_routes(logical_routes,
                                                      args.src_cloud,
                                                      args.dst_cloud,
                                                      args.include_nearby_as_locations,
                                                      args.output)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()
