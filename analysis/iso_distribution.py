import ast
import sys
import argparse
from itdk_geo import load_itdk_node_ip_to_id_mapping, parse_node_geo_as_dataframe
from carbon_client import get_carbon_region_from_coordinate


def convert_ip_to_coordinate(ip_address, node_ip_to_id, node_geo_df):
    """given an ip address and try to change it to a coordinate, 
    this function is skipping node without geo coordinates"""

    # Convert a IP address to a node ID using the node_ip_to_id dictionary
    node_id = node_ip_to_id[ip_address]

    # skipping node without geo coordinate
    if node_id not in node_geo_df.index:
        print(f'Node ID {node_id} not found in node_geo_df', file=sys.stderr)
        return None
    # Convert node ID to a coordinate using the node_geo_df dictionary
    row = node_geo_df.loc[node_id]
    return (row['lat'], row['long'])


def get_all_coordinates_by_region(cloud) -> dict[str, list[tuple[float, float]]]:
    if cloud == 'aws':
        matched_nodes_filename = 'matched_nodes.aws.by_region.txt'
    elif cloud == 'gcloud':
        matched_nodes_filename = 'matched_nodes.gcloud.by_region.txt'
    else:
        raise ValueError(f'Unsupported cloud {cloud}')

    node_ip_to_id = load_itdk_node_ip_to_id_mapping()
    node_geo_df = parse_node_geo_as_dataframe()

    with open(matched_nodes_filename) as file:
        dict_str = file.read()
        d_by_region = ast.literal_eval(dict_str)

    coordinates_by_region = {}
    for region, d_node_to_matches in d_by_region.items():
        coordinates = []
        for node_id in d_node_to_matches:
            for _, ip in d_node_to_matches[node_id]:
                # if the ip can be transform into coordinates, append it, otherwise skip it.
                ip_coordinate = convert_ip_to_coordinate(
                    ip, node_ip_to_id, node_geo_df)
                if ip_coordinate:
                    coordinates.append(ip_coordinate)
        coordinates_by_region[region] = coordinates
        print(
            f'Found {len(coordinates)} coordinates for {cloud}:{region}.', file=sys.stderr)

    return coordinates_by_region


def convert_all_coordinates_to_isos(coordinates_by_region: dict[str, list[tuple[float, float]]]) -> dict[str, list[str]]:
    isos_by_region = {}

    for region, list_of_coordinates in coordinates_by_region.items():
        region_iso_list = [get_carbon_region_from_coordinate(
            coordinate) for coordinate in list_of_coordinates]
        isos_by_region[region] = region_iso_list

    return isos_by_region


def get_iso_occurence_by_region(isos_by_region: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    iso_occurence_by_region = {}
    for region, iso_list in isos_by_region.items():
        region_iso_occurence = {}
        for iso in iso_list:
            region_iso_occurence[iso] = region_iso_occurence.get(iso, 0) + 1
        iso_occurence_by_region[region] = region_iso_occurence
    return iso_occurence_by_region


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cloud', required=True,
                        choices=['aws', 'gcloud'], help='The cloud provider you wish to get the iso occurence')

    return parser.parse_args()


def main():
    # input set can be aws or gcloud, to filter the corresponding data
    args = parse_args()

    # change region to a dictionary of coordinates
    coordinates_by_region = get_all_coordinates_by_region(args.cloud)

    # convert coordinates to ISOs by Region
    isos_by_region = convert_all_coordinates_to_isos(coordinates_by_region)

    # do stastics for ISOs distribution for each region
    iso_occurence_by_region = get_iso_occurence_by_region(isos_by_region)

    # print out the result or save to a file
    for region, iso_occurence in iso_occurence_by_region.items():
        print(f"Region {region} has iso distributions: {iso_occurence}")


if __name__ == '__main__':
    main()
