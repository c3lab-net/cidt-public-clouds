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

- (Optional) We can visualize the routes using the plot script:
```Shell
./plot.routes.distribution.py --routes_file routes.aws.us-west-1.us-east-1.by_geo
```

- Now with the routes in `(lat,lon)-coordinate` format, we can look up the carbon region or ISO (independent system operator) information with our carbon API.
```Shell
./carbon_client.py --convert-latlon-to-carbon-region --routes_file routes.aws.us-west-1.us-east-1.by_geo > routes.aws.us-west-1.us-east-1.by_iso
```

- Finally, we can export the distribution for easy lookup later (e.g. in a database).
```Shell
./carbon_client.py --export-routes-distribution --routes_file routes.aws.us-west-1.us-east-1.by_iso > routes.aws.us-west-1.us-east-1.by_iso.distribution
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
```Shell
set -e
./itdk_geo.py --convert-ip-to-latlon --routes_file region_pair.by_ip/routes.*.by_ip --outputs
chmod 440 routes.*.by_geo
for file in routes.*.by_geo; do
    echo "Processing $file ..."
    name="$(basename "$file" ".by_geo")"
    ./carbon_client.py --convert-latlon-to-carbon-region --routes_file $file > $name.by_iso
    ./carbon_client.py --export-routes-distribution --routes_file $name.by_iso > $name.by_iso.distribution
    chmod 440 $name.by_iso $name.by_iso.distribution
done

mkdir region_pair.by_geo region_pair.by_iso region_pair.by_iso.distribution
mv routes.*.by_geo region_pair.by_geo/
mv routes.*.by_iso region_pair.by_iso/
mv routes.*.by_iso.distribution region_pair.by_iso.distribution/
```

## Clean up noisy routes

Due to inaccurate IP ranges or geolocation lookup, there can be routes that don't conform to the rough geographical regions, or carbon regions.
To get around this problem, we can get the ISO distribution for each cloud region, and manually pick the "correct" one by checking the map and (most of the time) picking the majority.
```Shell
./cloud_region_distribution.py --cloud aws --of-iso > iso_distribution.aws.txt
```

(Optional) We can also get a distribution of the geo-coordinates of each region based on the matched IPs, and manually inspect the result to get the location in city/state/country.
```Shell
./cloud_region_distribution.py --cloud aws --of-coordinate > gps_distribution.aws.txt
```

After manual inspection, we can save the result in [CSV files](./results/iso_distributions/) and later use this information to prune the routes (by the correct src/dst ISOs).
```Shell
./carbon_client.py --export-routes-distribution --filter-iso-by-ground-truth --iso-ground-truth-csv ./results/iso_distributions/iso_distribution.all.csv --src-cloud aws --src-region us-west-1 --dst-cloud aws --dst-region us-east-1 --routes_file routes.aws.us-west-1.us-east-1.by_iso > routes.aws.us-west-1.us-east-1.by_iso.distribution
```

## (Optional) Utility scripts
When splitting calculation among multiple nodes, sometimes it's desireable to split a single region into multiple parts, as different region has different number of IPs.
```Shell
./split_cloud_region.matched_nodes.py -c gcloud --region us-central1 --parts 3 > matched_nodes.gcloud.by_region.modified.txt
```