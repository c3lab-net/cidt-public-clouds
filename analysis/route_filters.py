import ast
import sys
import argparse
from itdk_geo import load_itdk_node_ip_to_id_mapping, parse_node_geo_as_dataframe
from carbon_client import get_carbon_region_from_coordinate

def convert_ip_to_latlon(ip_addresses, node_ip_to_id, node_geo_df):
        # Convert each IP address to a node ID using the node_ip_to_id dictionary
    node_id = node_ip_to_id[ip_addresses]

    # Convert node IDs to latitude and longitude using the node_geo_df dictionary

        # _debug_
    if node_id not in node_geo_df.index:
        print(f'Node ID {node_id} not found in node_geo_df', file=sys.stderr)
        return None
    row = node_geo_df.loc[node_id]
    return (row['lat'], row['long'])



def get_all_regions_ips(cloud) -> dict[str, list[tuple[float, float]]]:
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

    ips_by_region = {}
    for region, d_node_to_matches in d_by_region.items():
        ips = []
        for node_id in d_node_to_matches:
            for ip_prefix, ip in d_node_to_matches[node_id]:
                if convert_ip_to_latlon(ip, node_ip_to_id, node_geo_df):
                    ips.append(convert_ip_to_latlon(ip, node_ip_to_id, node_geo_df))
        ips_by_region[region] = ips
        print(f'Found {len(ips)} IPs for {cloud}:{region}.', file=sys.stderr)

    return ips_by_region

def transform_dict(input_dict: dict[str, list[tuple[float, float]]]) -> dict[str, list[str]]:
    result_dict = {}
    for key, list_of_tuples in input_dict.items():
        transformed_list = [get_carbon_region_from_coordinate(tup) for tup in list_of_tuples]
        result_dict[key] = transformed_list
    return result_dict

def calculate_appearance_times(input_dict: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    appearance_dict = {}
    for key, values in input_dict.items():
        # Using a defaultdict to automatically initialize counts to 0
        counts = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        appearance_dict[key] = counts
    return appearance_dict

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cloud', required=True, choices=[ 'aws', 'gcloud' ], help='The source cloud provider')


    return parser.parse_args()

def main():
    # input set can be aws or gcloud, to filter the corresponding data
    args = parse_args()

    # change cluster to a ip list
    src_ips = get_all_regions_ips(args.cloud)

    # change ip to ISO
    src_carbon_region = transform_dict(src_ips)

    # do stastics for ISOs
    result = calculate_appearance_times(src_carbon_region)
    for key, values in result.items():
        print(f"cluster {key} has router statics: {values}")
    

if __name__ == '__main__':
    main()