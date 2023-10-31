# CAIDA ITDK Analysis

This directory holds the analysis script using the CAIDA ITDK dataset and public cloud IP range/prefix data.

## Usage

- First step is to download the ITDK dataset into [data](../data) directory. Adjust the filenames in `itdk_*.py` files accordingly.
- Next step is to find out the matching IP addresses with a cloud provider, or region (`-r us-west-1`):
```Shell
./itdk_nodes.py --match_cloud_ips_with_itdk -c aws > matched_nodes.aws.by_node.txt
```

- Once we we have this mapping from node id to a list of matched IPs `(matched IP, IP prefix, region)`, we convert them to a `region -> node_id -> [(prefix, ip)]` dictionary via:
```Shell
./itdk_nodes.py --convert_to_by_region -c aws --matched_nodes_file matched_nodes.aws.by_node.txt > matched_nodes.aws.by_region.txt
```

- We can then use this to calculate region-to-region routes by running Dijkstra's algorithm from each source IP to the set of destination IPs. The graph comes from the ITDK node/link dataset, which is quite large and thus this step can take minutes to hours, depending on the number of IPs.
```Shell
./itdk_links.py --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1 1> routes.aws.us-west-1.us-east-1.by_ip 2> routes.aws.us-west-1.us-east-1.err
```
This produces a file that contains one route on each line, for each source IP, and the route is represented by a list of IP addresses.

- We next convert each IP address to a (lat, long) geocoordinate using the ITDK `.nodes.geo` database:
```Shell
./itdk_geo.py --convert-ip-to-latlon --routes_file routes.aws.us-west-1.us-east-1.by_ip 1> routes.aws.us-west-1.us-east-1.by_geo
```

- (Optional) We can visualize the routes using the plot script:
```Shell
./plot.routes.distribution.py --routes_file routes.aws.us-west-1.us-east-1.by_geo
```

- Now with the routes in `(lat,lon)-coordinate` format, we can look up the carbon region or ISO (independent system operator) information with our carbon API.
```Shell
./carbon_region.py --convert-latlon-to-carbon-region --routes_file routes.aws.us-west-1.us-east-1.by_geo > routes.aws.us-west-1.us-east-1.by_iso
```

- Finally, we can export the distribution for easy lookup later (e.g. in a database).
```Shell
./carbon_client.py --export-routes-distribution --routes_file routes.aws.us-west-1.us-east-1.by_iso > routes.aws.us-west-1.us-east-1.by_iso.distribution
```

## Clean up noisy routes

Due to inaccurate IP ranges or geolocation lookup, there can be routes that don't conform to the rough geographical regions, or carbon regions.
To get around this problem, we can get the ISO distribution for each cloud region, and manually pick the "correct" one by checking the map and (most of the time) picking the majority.
```Shell
./iso_distribution.py --cloud aws > iso_distribution.aws.txt
```

After manual inspection, we can save the result in [CSV files](./results/iso_distributions/) and later use this information to prune the routes (by the correct src/dst ISOs).
```Shell
./carbon_client.py --export-routes-distribution --filter-iso-by-ground-truth --iso-ground-truth-csv ./results/iso_distributions/iso_distribution.aws.csv --src-region us-west-1 --dst-region us-east-1 --routes_file routes.aws.us-west-1.us-east-1.by_iso > routes.aws.us-west-1.us-east-1.by_iso.distribution
```
