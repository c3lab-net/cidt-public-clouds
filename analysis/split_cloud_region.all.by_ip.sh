#!/bin/bash

# This script renames and splits the results of .by_ip files that cover multiple regions into separate files by region pair, as indicated by the comment line.
#   One .by_ip file, e.g. hostname1.numa0.routes.aws.af-south-1.aws.all.by_ip can contains multiple sections, each covers one region pairs, as indicated by the comment line like this: # aws:af-south-1 -> aws:us-east-1, and the following lines are the routes between these two regions.
#   This script to put this section into a separate file, named by the region pair, like this: routes.aws.af-south-1.aws.us-east-1.by_ip

mkdir rawdata rawdata.useful
chmod 440 *.numa*.routes.*.all.{by_ip,err}
mv *.numa*.routes.*.all.{by_ip,err} rawdata/

for file in rawdata/*.numa*.routes.*.by_ip; do
    pretty_name="$(echo $(basename $file) | cut -d. -f 3- | sed 's/\.gcp\./.gcloud./g')"
    (set -x; ln -s ../$file rawdata.useful/$pretty_name)
done

# Adjust symlinks in rawdata.useful/ if needed, e.g. to get rid of partial files.

mkdir region_pair.by_ip
for file in ./rawdata.useful/routes.*.all.by_ip; do
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
