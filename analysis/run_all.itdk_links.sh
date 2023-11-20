#!/bin/bash

# This script runs all the itdk_link.py commands for the pairs of regions we're interested in.
#   Adjust the parameters below and parallelize the for loops as needed.

# Regions we're interested in
export AWS_REGIONS="eu-central-1 eu-north-1 eu-south-1 eu-west-1 eu-west-2 eu-west-3 ca-central-1 us-east-1 us-east-2 us-west-1 us-west-2 sa-east-1 af-south-1 ap-northeast-1 ap-northeast-2 ap-northeast-3 ap-south-1 ap-southeast-1 ap-southeast-2"
export GCP_REGIONS="europe-central2 europe-north1 europe-west1 europe-west2 europe-west3 europe-west4 europe-west6 northamerica-northeast1 northamerica-northeast2 southamerica-east1 southamerica-west1 us-central1 us-central2 us-east1 us-east4 us-east7 us-west1 us-west2 us-west3 us-west4 asia-east1 asia-northeast1 asia-northeast2 asia-northeast3 asia-south1 asia-south2 asia-southeast1 australia-southeast1 australia-southeast2"
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
