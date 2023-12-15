# Inter-cloud-region Route Analysis

This directory holds the analysis script for inter-cloud-region routes, using primarily the CAIDA ITDK dataset, together with public cloud IP range/prefix data. You can find more details about these dataset in the [data](../data/) directory.

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

### Single region pair

- We can then use this to calculate region-to-region routes by running Dijkstra's algorithm from each source IP to the set of destination IPs. The graph comes from the ITDK node/link dataset, which is quite large and thus this step can take minutes to hours, depending on the number of IPs.
```Shell
./itdk_links.py --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1 1> routes.aws.us-west-1.us-east-1.by_ip 2> routes.aws.us-west-1.us-east-1.err
```
This produces a file that contains one route on each line, for each source IP, and the route is represented by a list of IP addresses.

**Note** that this part can take a long time, including both the time to load node (3min) and geo files (30s), build the graph (25min) and run Dijkstra (variable dependings on the # of inputs). We've parallelized the Dijkstra code, but not the building graph part, so it's better to invoke this on a large # of regions, or an entire cloud to amortize the startup cost, and later split the results.

- We next convert each IP address to a (lat, long) geocoordinate using the ITDK `.nodes.geo` database:
```Shell
./itdk_geo.py --convert-ip-to-latlon --routes_file routes.aws.us-west-1.us-east-1.by_ip 1> routes.aws.us-west-1.us-east-1.by_geo
```

- (Supplemental) We can further improve the accuracy of the traceroute-level dataset by querying iGDB dataset, provided by an external program.
```Shell
mv routes.aws.us-west-1.us-east-1.by_geo routes.aws.us-west-1.us-east-1.by_geo.logical
./igdb_client.py --convert-to-physical-hops --routes_file routes.aws.us-west-1.us-east-1.by_geo.logical -o routes.aws.us-west-1.us-east-1.by_geo.physical
awk -F '\t' '{print $1}' routes.aws.us-west-1.us-east-1.by_geo.physical > routes.aws.us-west-1.us-east-1.by_geo
```

- (Optional) We can visualize the routes using the plot script:
```Shell
./plot.routes.single_region_pair.py --routes_file routes.aws.us-west-1.us-east-1.by_geo
```

- Now with the routes in `(lat,lon)-coordinate` format, we can look up the carbon region or ISO (independent system operator) information with our carbon API.
```Shell
./carbon_client.py --convert-latlon-to-carbon-region --routes_file routes.aws.us-west-1.us-east-1.by_geo > routes.aws.us-west-1.us-east-1.by_iso
```

- Finally, we can export the distribution of geo-coordinates or ISOs for easy lookup later (e.g. in a database).
```Shell
# (optionally, include additional metrics and remove duplicate consecutive hops) --include hop_count distance_km --remove-duplicate-consecutive-hops
# (optionally, include iGDB route fiber information using earlier files) --include fiber_wkt_paths fiber_types --physical-routes-tsv routes.aws.us-west-1.us-east-1.by_geo.physical
./distribution.routes.py --export-routes-distribution --routes_file routes.aws.us-west-1.us-east-1.by_geo > routes.aws.us-west-1.us-east-1.by_geo.distribution
./distribution.routes.py --export-routes-distribution --routes_file routes.aws.us-west-1.us-east-1.by_iso > routes.aws.us-west-1.us-east-1.by_iso.distribution
```

### All region pairs (batch execution)

We created a [batch execution script](./run_all.itdk_links.sh) to loop through all the region pairs that we're interested in and run Dijkstra's in parallel across multiple machines.
This can take days even across multiple machines (with dozens of cores on each), so adjust the script to match your distributed execution platform as needed.
```Shell
./run_all.itdk_links.sh
```
This will generate a list of files (named `hostname.numa{0,1}.routes.{aws,gcloud}.*.{aws,gcloud}.all.by_ip`) from one region (e.g. AWS:us-west-1) to all destination regions in one file, separated by comment lines.

We can then use this script to organize and split all these files into one file per source/destination region pair, e.g. `routes.aws.us-east-1.aws.eu-west-1.by_ip`.
```Shell
./split_cloud_region.all.by_ip.sh
```
This will put the existing files in a sub-directory called `rawdata` and store all the per-region-pair `.by_ip` files into a sub-directory `region_pair.by_ip`.

Afterwards, we can run IP-to-geo-coordinate, geo-coordinate-to-ISO and ISO distribution steps in parallel.
Note that IP-to-geo script accepts multiple input files, due to its overhead of loading the GEO dataset. The other two scripts can be easily ran in a for loop.
Also see the below section ("Clean up noisy routes") for details on filtering by ground truth.
```Shell
./run_all.conversions.sh
```

- (Optional) We can also plot the distribution of the routes statistics like `hop_count` and `distance_km` using this all-region-pairs plotting script. You can want to update the region filters for PDF plots, as it's on a per-region basis.
```Shell
# Optionally, filter by adding --src-cloud aws/gcloud --dst-cloud aws/gcloud, or also by regions: --src-region ... --dst-region ...
./plot.routes.all_region_pairs.py --plot-heatmap --metrics hop_count --dirpath ./region_pair.by_geo.distribution/
./plot.routes.all_region_pairs.py --plot-heatmap --metrics distance_km --dirpath ./region_pair.by_geo.distribution/
./plot.routes.all_region_pairs.py --plot-pdfs --metrics hop_count --dirpath ./region_pair.by_geo.distribution/ --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1
./plot.routes.all_region_pairs.py --plot-pdfs --metrics distance_km --dirpath ./region_pair.by_geo.distribution/ --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1
```

### Traceroute from inside cloud regions

Note that the CAIDA ITDK dataset is collected from public ARK probe endpoints, and thus may not observe the same set of routes as from inside the cloud. Thus, to improve the route accuracy, we can run `traceroute` directly from each cloud region, to all other cloud regions.

In order to run traceroute, we need to get a list of responsive hosts inside each region. We can get this by sending ICMP echo requests to each host inside that region based on the [IP ranges](../data/) list. Since they are very large (a few dozens per region, each up to /15 prefix), we use [zmap](https://github.com/zmap/zmap) to run ICMP echo ping in parallel, and limit the results to about 1000 per region.

Given the IP ranges/prefixes list, we can generate the per-region input file and run `zmap` using this script: `scan_ip_prefix.sh`.
Note that `zmap` randomly orders and samples from the entire input IP space. We can verify the output distribution using `scan_ip_distribution.py`.

## Clean up noisy routes

Due to inaccurate IP ranges or geolocation lookup, there can be routes that don't conform to the rough geographical regions, or carbon regions / ISOs.

### By ISO

To get around this problem, we can get the ISO distribution for each cloud region, and manually pick the "correct" one by checking the map and (most of the time) picking the majority.
```Shell
./distribution.cloud_region.py --cloud aws --of-iso > iso_distribution.aws.txt
./distribution.cloud_region.py --cloud gcloud --of-iso > iso_distribution.gcloud.txt
```

After manual inspection, we can save the result in a [CSV file](./results/iso_distributions/iso_distribution.all.csv) and later use this information to prune the routes (by the correct src/dst ISO of the respective region).
```Shell
./carbon_client.py --convert-latlon-to-carbon-region --filter-iso-by-ground-truth --iso-ground-truth-csv ./results/iso_distributions/iso_distribution.all.csv --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1 --routes_file routes.aws.us-west-1.us-east-1.by_geo > routes.aws.us-west-1.us-east-1.by_iso
```

### By geo-coordinate

Similarly, we can also get a distribution of the geo-coordinates of each region based on the matched IPs, and manually inspect the result to get the latitude/longitude similar to the above ISO distributions.
```Shell
./distribution.cloud_region.py --cloud aws --of-coordinate > gps_distribution.aws.txt
./distribution.cloud_region.py --cloud gcloud --of-coordinate > gps_distribution.gcloud.txt
```

Again, we can save the result in a [CSV file](./results/geo_distributions/geo_distribution.all.csv) and later use this information as a ground truth to prune the routes (by the correct src/dst *ISO based on the geo coordinate* of the respective region, this is because coordinate equality check is too strict).
```Shell
./itdk_geo.py --convert-ip-to-latlon --filter-geo-coordinate-by-ground-truth --geo-coordinate-ground-truth-csv ./results/geo_distributions/geo_distribution.all.csv --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1 --routes_file routes.aws.us-west-1.us-east-1.by_ip 1> routes.aws.us-west-1.us-east-1.by_geo
```

Note that when we filter at the geo-coordinate stage, we no longer need to filter again at the ISO stage, as both are comparing the ISOs of the first and last hop of a route with the source and destination ISOs. Hence the omission in the earlier batch execution script.

## (Optional) Utility scripts
When splitting calculation among multiple nodes, sometimes it's desireable to split a single region into multiple parts, as different region has different number of IPs.
```Shell
./split_cloud_region.matched_nodes.py -c gcloud --region us-central1 --parts 3 > matched_nodes.gcloud.by_region.modified.txt
```