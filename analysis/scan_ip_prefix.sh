#!/bin/bash

# This script uses nmap to scan the provided ip prefix to find out the responsive hosts


# Parse input
if [ $# -lt 1 ]; then
    echo "Usage: $0 <ip_prefix-file>"
    exit 1
fi

# Read the ip prefix file
ip_prefix_file="$1"

if [[ "$ip_prefix_file" == *"aws"* ]]; then
    IS_AWS=true
elif [[ "$ip_prefix_file" == *"gcloud"* ]]; then
    IS_GCLOUD=true
else
    echo "Unknown ip prefix file"
    exit 1
fi

get_regions()
{
    if [ "$IS_AWS" = true ]; then
        jq -r '.prefixes[].region' "$ip_prefix_file" | sort -u | grep -v GLOBAL
    elif [ "$IS_GCLOUD" = true ]; then
        jq -r '.prefixes[].scope' "$ip_prefix_file" | sort -u | grep -v global
    fi
}

parse_ip_prefixes_into_regions() {
    if [ "$IS_AWS" = true ]; then
        echo "Detected aws region file"
        regions="$(get_regions)"
        for region in $regions; do
            echo "Region: $region"
            jq -r '.prefixes[] | select(.region == "'"$region"'") | .ip_prefix' "$ip_prefix_file" | grep -v null | sort -u > ip-prefixes.aws."$region".txt
        done
    elif [ "$IS_GCLOUD" = true ]; then
        echo "Detected gcloud region file"
        regions="$(get_regions)"
        for region in $regions; do
            echo "Region: $region"
            jq -r '.prefixes[] | select(.scope == "'"$region"'") | .ipv4Prefix' "$ip_prefix_file" | grep -v null | sort -u > ip-prefixes.gcloud."$region".txt
        done
    fi
}

scan_region()
{
    cloud="$1"
    region="$2"

    input="ip-prefixes."$cloud.$region".txt"
    output="responsive_hosts."$cloud.$region".txt"

    echo "Scanning $cloud:$region using zmap ..."
    echo "$input -> $output"

    # We can probably just sample from the entire region, since zmap randomly samples from all ip prefixes
    (set -x; sudo zmap -i eno1 --probe-module=icmp_echoscan --max-results=1000 -w "$input" >> "$output")
    : '
    echo -n > "$output"
    index=0
    for ip_prefix in $(cat "$input"); do
        sudo zmap -q -i eno1 --probe-module=icmp_echoscan -B 500M --max-results=100 "$ip_prefix" > "$output.$index"
        [ $? -eq 0 ] || echo >&2 "zmap scan for $ip_prefix failed"
        index=$((index+1))
    done
    wait
    cat "$output".* > "$output"
    rm "$output".*
    #'
}

scan_for_responsive_hosts()
{
    regions="$(get_regions)"
    if [ "$IS_AWS" = true ]; then
        cloud="aws"
    elif [ "$IS_GCLOUD" = true ]; then
        cloud="gcloud"
    fi
    for region in $regions; do
        scan_region "$cloud" "$region"
    done
}

list_all_regions()
{
    regions="$(get_regions)"
    for region in $regions; do
        echo "$region"
    done
}

list_all_regions

parse_ip_prefixes_into_regions "$ip_prefix_file"
scan_for_responsive_hosts
