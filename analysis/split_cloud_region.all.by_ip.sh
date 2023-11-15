#!/bin/bash

# This script splits the results of .by_ip files that cover multiple regions into separate files by region pair, as indicated by the comment line.
#   One .by_ip file, e.g. routes.aws.af-south-1.aws.all.by_ip can contains multiple sections, each covers one region pairs, as indicated by the comment line like this: # aws:af-south-1 -> aws:us-east-1, and the following lines are the routes between these two regions.
#   This script to put this section into a separate file, named by the region pair, like this: routes.aws.af-south-1.aws.us-east-1.by_ip

mkdir rawdata
chmod 440 routes.*.all.{by_ip,err}
mv routes.*.all.{by_ip,err} rawdata/

mkdir region_pair.by_ip
for file in ./rawdata/routes.*.all.by_ip; do
    # Split the by_ips into files by region pair, as indicated by the comment line: # aws:af-south-1 -> aws:us-east-1
    awk '
    /^#/ {
        gsub(/^# /, "");
        gsub(/:/, ".");
        gsub(/ -> /, ".");
        filename = "routes." $0 ".by_ip";
        next;
    }
    { print > filename }
    ' "$file"
done
chmod 440 routes.*.by_ip
mv routes.*.by_ip region_pair.by_ip/
