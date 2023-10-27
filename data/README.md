## Data source

### [CAIDA ITDK](./caida-itdk/)

This is the ITDK dataset from 2022-03 release. More info can be found in the [caida-itdk](./caida-itdk/) directory.

### [Public cloud info](./cloud/)

#### IP ranges
- [AWS](./cloud/ip-ranges.aws.json): https://docs.aws.amazon.com/vpc/latest/userguide/aws-ip-ranges.html
- [Google cloud](./cloud/ip-ranges.gcloud.json): https://www.gstatic.com/ipranges/cloud.json


#### Geolocation
- [AWS](./cloud/geolocation.aws.csv):
    - https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-regions-availability-zones.html#region-name ,
    - https://aws.amazon.com/about-aws/global-infrastructure/ -> List view, or
    - https://www.aws-services.info/regions.html
- [Google cloud](./cloud/geolocation.gcloud.csv): https://cloud.google.com/compute/docs/regions-zones
