#!/bin/bash

mkdir rawdata
chmod 440 routes.*.all.{by_ip,err}
mv routes.*.all.{by_ip,err} rawdata/

mkdir region_pair.by_ip
for file in ./rawdata/routes.*.all.by_ip; do
    # Split the by_ips into files by region pair, as indicated by the comment line: # AWS:us-east-1 -> Azure:us-east
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
