#!/usr/bin/env python3

import argparse
import collections
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.markers as markers
from mpl_toolkits.basemap import Basemap

from common import get_routes_from_file

def plot_route_hop_count_distribution(routes: list[list], filename):
    num_entries_per_line = [len(route) for route in routes]
    # Sort the list of entry counts
    num_entries_per_line.sort()

    # Calculate the CDF
    cdf = [i / len(num_entries_per_line) for i in range(1, len(num_entries_per_line) + 1)]

    # Plot the CDF
    plt.plot(num_entries_per_line, cdf, marker='.', linestyle='none')
    plt.xlabel('Router hop count')
    plt.ylabel('CDF')
    plt.title('CDF of router hop count')
    plt.grid(True)
    plt.savefig(f'{filename}.hop_count.cdf.png')

def assert_route_is_in_latlon_format(routes):
    for route in routes:
        for entry in route:
            assert len(entry) == 2, f'Entry {entry} is not in lat/lon format'

def plot_routes_on_worldmap(routes: list[list[tuple[float, float]]], filename):
    # Each route is a list of (lat, lon) coordinates that will be connected hop-by-hop
    # Create a Basemap object
    map = Basemap(projection='mill', llcrnrlat=-90, urcrnrlat=90, llcrnrlon=-180, urcrnrlon=180, resolution='c')

    # Create a figure and axis for the map
    fig, ax = plt.subplots(figsize=(20, 10))

    # Plot the routes
    for line in routes:
        lats, lons = zip(*line)
        x, y = map(lons, lats)
        # ax.plot(x, y, marker='o')
        ax.plot(x, y, color='gray', linewidth=0.5)
        ax.scatter(x[:1], y[:1], marker=markers.MarkerStyle('o'), color='red')
        ax.scatter(x[-1:], y[-1:], marker=markers.MarkerStyle('o'), color='green')

    # # Set labels for the start and end points
    # for i, line in enumerate(routes):
    #     start = line[0]
    #     end = line[-1]
    #     x_start, y_start = map(start[1], start[0])
    #     x_end, y_end = map(end[1], end[0])
    #     ax.annotate(f'Start {i+1}', xy=(x_start, y_start), xytext=(x_start + 1000000, y_start + 1000000))
    #     ax.annotate(f'End {i+1}', xy=(x_end, y_end), xytext=(x_end + 1000000, y_end + 1000000))

    # Draw coastlines and countries
    map.drawcoastlines()
    map.drawcountries()

    # Set title
    ax.set_title('Connected Coordinates on a World Map')

    # Show the map
    # plt.show()
    plt.savefig(f'{filename}.world_map.png')

def group_routes_by(routes: list[list], group_by: str):
    if group_by == 'hopcount':
        values = [len(route) for route in routes]
        pass
    elif group_by == 'hops':
        values = [tuple(route[1:-1]) for route in routes]
        pass
    else:
        raise ValueError(f'Unknown group_by value: {group_by}')
    return sorted(collections.Counter(values).items(), key=lambda x: x[1], reverse=True)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--routes_file', required=True, type=str, help='The routes file, each line contains a list that represents a route.')
    parser.add_argument('--plot_hop_count_cdf', action='store_true')
    parser.add_argument('--plot_routes_on_map', action='store_true')
    parser.add_argument('--group_by', choices=['hopcount', 'hops'], help='Rank the routes by hop count or actual hops')
    parser.add_argument('--plot_carbon_timeseries', type=datetime.fromisoformat)
    parser.add_argument('--start_time', type=datetime.fromisoformat)
    parser.add_argument('--end_time', type=datetime.fromisoformat)
    args = parser.parse_args()

    if args.plot_carbon_timeseries and not (args.start_time and args.end_time):
        parser.error('--start_time and --end_time must be specified when --plot_carbon_timeseries is specified')

    return args

def plot_carbon_timeseries(routes: list[list[tuple]], start_time: datetime, end_time: datetime):
    # TODO: Aggregate the routes
    raise NotImplementedError()
    # Fetch carbon intensity for the time range and locations on each route
    # Calculate carbon intensity of data transfer for each route
    # Weight average the CIDT across all routes
    # Plot the weighted average CIDT over time

def main():
    args = parse_args()
    routes = get_routes_from_file(args.routes_file)
    file_basename = args.routes_file.removesuffix('.by_ip')
    if args.plot_hop_count_cdf:
        plot_route_hop_count_distribution(routes, file_basename)
    elif args.plot_routes_on_map:
        assert_route_is_in_latlon_format(routes)
        plot_routes_on_worldmap(routes, file_basename)
    elif args.group_by:
        route_groups = group_routes_by(routes, args.group_by)
        for count, route in route_groups:
            print(f'{count} occurences: {route}')
    elif args.plot_carbon_timeseries:
        plot_carbon_timeseries(routes, args.start_time, args.end_time)
    else:
        raise ValueError('No action specified')

if __name__ == '__main__':
    main()

