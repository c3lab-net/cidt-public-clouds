## Data source

### [CAIDA ITDK](./caida-itdk/)

[Macroscopic Internet Topology Data Kit (ITDK)](https://www.caida.org/catalog/datasets/internet-topology-data-kit/)
> The ITDK contains data about connectivity and routing gathered from a large cross-section of the global Internet. This dataset is useful for studying the topology of the Internet at the router-level, among other uses.

We use this dataset to reconstruct the Internet router connectivity graph and from there, infer the inter-cloud paths based on the IP prefixes of each cloud region (see next section).

The ITDK dataset we use is from the 2022-03 release. More info on this dataset can be found in the [caida-itdk](./caida-itdk/) directory.

### [Maxmind](./maxmind/)
Maxmind is a commericial IP-to-geolocation database and we use the lite version from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data.
Download the database and extract the `.mmdb` file into [`maxmind`](./maxmind/) directory. It's named `GeoLite2-City.mmdb` in our case; if it's different, you may need to adjust the filename in the run scripts.

### [Public cloud info](./cloud/)

#### IP ranges
- [AWS](./cloud/ip-ranges.aws.json): https://docs.aws.amazon.com/vpc/latest/userguide/aws-ip-ranges.html
- [Google cloud](./cloud/ip-ranges.gcloud.json): https://www.gstatic.com/ipranges/cloud.json


#### Geolocation
- [AWS](./cloud/geolocation.aws.csv):
    - https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html#region-name ,
    - https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.RegionsAndAvailabilityZones.html ,
    - https://aws.amazon.com/about-aws/global-infrastructure/ -> List view, or
    - https://www.aws-services.info/regions.html
- [Google cloud](./cloud/geolocation.gcloud.csv): https://cloud.google.com/compute/docs/regions-zones
