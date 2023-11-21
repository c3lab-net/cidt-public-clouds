#!/bin/bash

cd "$(dirname "$0")"

# This script runs all the itdk_link.py commands for the pairs of regions we're interested in.
#   Adjust the parameters below and parallelize the for loops as needed.

source ./run_all.shared.sh

# export SRC_REGION="TBD"
export HOSTNAME="$(hostname -s)"

# Note: Each call is meant to be run over multiple console windows and over multiple machines.
#   Remove the tee redirects if you want to run them in the background and don't want to see output in console.
#   Use other batch execution systems if you want to automatically run them on multiple machines.

run_single_src_region_to_entire_cloud()
{
    numanode=$1
    src_cloud=$2
    src_region=$3
    dst_cloud=$4
    if [ $dst_cloud = "aws" ]; then
        dst_regions="$AWS_REGIONS"
    elif [ $dst_cloud = "gcloud" ]; then
        dst_regions="$GCP_REGIONS"
    else
        echo "ERROR: unknown dst_cloud=$dst_cloud"
        exit 1
    fi
    numactl --cpunodebind=$numanode --membind=$numanode \
        /usr/bin/time -v \
        ./itdk_links.py --src-cloud $src_cloud --src-regions $src_region \
                        --dst-cloud $dst_cloud --dst-regions $(echo "$dst_regions") \
            1> >(tee $HOSTNAME.numa$numanode.routes.$src_cloud.$src_region.$dst_cloud.all.by_ip) \
            2> >(tee $HOSTNAME.numa$numanode.routes.$src_cloud.$src_region.$dst_cloud.all.err >&2)
}

run_all()
{
    # From AWS
    for src_region in $(echo $AWS_REGIONS); do
        run_single_src_region_to_entire_cloud 0 aws $src_region aws
        run_single_src_region_to_entire_cloud 1 aws $src_region gcloud
    done

    # From gcloud
    for src_region in $(echo $GCP_REGIONS); do
        run_single_src_region_to_entire_cloud 0 gcloud $src_region aws
        run_single_src_region_to_entire_cloud 1 gcloud $src_region gcloud
    done
}

# Verification functions

# Check whether the filename indicates that the src and dst clouds are the same.
is_same_cloud_provider()
{
    file="$1"
    file="$(basename "$file")"
    name="$(echo "$file" | egrep -o 'routes\.(aws|gcp|gcloud)\.(.*)\.(aws|gcp|gcloud).all')"
    name="$(echo "$name" | sed 's/\.gcp\./.gcloud./g')"
    [ -z "$name" ] && return 1
    src_cloud="$(echo "$name" | awk -F '.' '{print $2}')"
    dst_cloud="$(echo "$name" | awk -F '.' '{print $(NF-1)}')"
    [ "$src_cloud" = "$dst_cloud" ]
}

verify_dijkstra_completion_count()
{
    file="$1"
    expected_count=$2

    # No self-paths if src and dst are in the same cloud, decrement by one
    is_same_cloud_provider "$file" && expected_count=$(($expected_count - 1))

    actual_count=$(grep -c "Dijkstra from .* to .* completed. Found .* paths in total." "$file")
    if [ $actual_count -ne $expected_count ]; then
        echo >&2 "ERROR: $file: expected $expected_count Dijkstra completions, but got $actual_count"
        # exit 1
    fi
}

verify_all()
{
    echo "Verifying Dijkstra completion counts in each file ..."

    for file in ./*.numa*.routes.*.aws.all.err; do
        echo "Checking $file"
        verify_dijkstra_completion_count $file $(echo "$AWS_REGIONS" | wc -w)
    done

    for file in ./*.numa*.routes.*.gcloud.all.err; do
        echo "Checking $file"
        verify_dijkstra_completion_count $file $(echo "$GCP_REGIONS" | wc -w)
    done

    echo "Done."
}

run_all
verify_all
