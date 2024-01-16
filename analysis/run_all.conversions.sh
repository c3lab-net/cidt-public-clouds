#!/bin/bash

# This script runs all the conversion of IP addresses to geo coordinates and then to carbon regions / ISOs.

cd "$(dirname "$0")"

WORK_DIR="."
IP_GEOLOCATION_ACCURACY_RADIUS=100
IGDB_INCLUDE_NEARBY_AS_LOCATIONS=0
GENERATE_ISO_FILES=0
USE_MAXMIND=0

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ip-geolocation-accuracy-radius)
      IP_GEOLOCATION_ACCURACY_RADIUS="$2"
      shift 2
      ;;
    --include-nearby-as-locations)
      IGDB_INCLUDE_NEARBY_AS_LOCATIONS=1
      shift
      ;;
    --generate-iso-files)
      GENERATE_ISO_FILES=1
      shift
      ;;
    --work-dir)
      WORK_DIR="$2"
      shift 2
      ;;
    --use-maxmind)
      USE_MAXMIND=1
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo >&2 "WORK_DIR=$WORK_DIR"
echo >&2 "IP_GEOLOCATION_ACCURACY_RADIUS=$IP_GEOLOCATION_ACCURACY_RADIUS"
echo >&2 "IGDB_INCLUDE_NEARBY_AS_LOCATIONS=$IGDB_INCLUDE_NEARBY_AS_LOCATIONS"
echo >&2 "GENERATE_ISO_FILES=$GENERATE_ISO_FILES"
echo >&2 "USE_MAXMIND=$USE_MAXMIND"

export WORK_DIR
export IP_GEOLOCATION_ACCURACY_RADIUS
export IGDB_INCLUDE_NEARBY_AS_LOCATIONS
export GENERATE_ISO_FILES
export USE_MAXMIND

ip_to_geo()
{
    # IP-to-geo conversion
    echo >&2 "Converting IP addresses to geo coordinates..."
    itdk_geo_extra_args=()
    if [ $USE_MAXMIND -ne 0 ]; then
        itdk_geo_extra_args+=(--maxmind-database ../data/maxmind/GeoLite2-City.mmdb)
        itdk_geo_extra_args+=(--accuracy-radius "$IP_GEOLOCATION_ACCURACY_RADIUS")
    fi
    ./itdk_geo.py --convert-ip-to-latlon --remove-duplicate-consecutive-hops --filter-geo-coordinate-by-ground-truth --geo-coordinate-ground-truth-csv ./results/geo_distributions/geo_distribution.all.csv "${itdk_geo_extra_args[@]}" --routes_file region_pair.by_ip/routes.*.by_ip --output-dir "$WORK_DIR" --outputs
    chmod 440 "$WORK_DIR"/routes.*.by_geo
}

process_region_by_geo()
{
    name="$1"

    echo >&2 "Processing $name ..."

    set -e

    # Call iGDB to convert logical hops to physical hops
    mv $name.by_geo $name.by_geo.logical
    igdb_client_args=()
    if [ $IGDB_INCLUDE_NEARBY_AS_LOCATIONS -ne 0 ]; then
        igdb_client_args+=(--include-nearby-as-locations)
    fi
    ./igdb_client.py --convert-to-physical-hops --preserve-igdb-api-cache --routes_file $name.by_geo.logical -o $name.by_geo.physical "${igdb_client_args[@]}"
    awk -F '\t' '{print $1}' $name.by_geo.physical > $name.by_geo

    # Geo distribution
    ./distribution.routes.py --export-routes-distribution --include hop_count distance_km fiber_wkt_paths fiber_types --physical-routes-tsv $name.by_geo.physical --routes_file "$name.by_geo" > "$name.by_geo.distribution"

    chmod 440 "$name.by_geo."{logical,physical} "$name.by_geo.distribution"

    if [ $GENERATE_ISO_FILES -eq 0 ]; then
        return
    fi

    # Geo-to-ISO conversion
    ./carbon_client.py --convert-latlon-to-carbon-region --routes_file "$name.by_geo" > "$name".by_iso
    # It is not necessary to filter again as we have filtered earlier. See notes at the end of "Clean up noisy routes" section.
    # src_cloud="$(echo "$name" | awk -F. '{print $2}')"
    # src_region="$(echo "$name" | awk -F. '{print $3}')"
    # dst_cloud="$(echo "$name" | awk -F. '{print $4}')"
    # dst_region="$(echo "$name" | awk -F. '{print $5}')"
    # ./carbon_client.py --convert-latlon-to-carbon-region --filter-iso-by-ground-truth --iso-ground-truth-csv ./results/iso_distributions/iso_distribution.all.csv --src-cloud "$src_cloud" --src-region "$src_region" --dst-cloud "$dst_cloud" --dst-region "$dst_region" --routes_file "$name.by_geo" > "$name".by_iso

    # ISO distribution
    ./distribution.routes.py --export-routes-distribution --routes_file "$name.by_iso" > "$name.by_iso.distribution"

    chmod 440 $name.by_iso $name.by_iso.distribution
}

export -f process_region_by_geo

process_raw_geo_data()
{
    for file in "$WORK_DIR"/routes.*.by_geo; do
        name="${file%.by_geo}"
        if [ -f "$name.by_geo.distribution" ]; then
            echo >&2 "Skipping $name.by_geo as it has been processed."
            continue
        fi

        echo "$name"
        # If you don't have GNU `parallel`, you can remove the pipe after `done` use this instead:
        # process_region_by_geo "$name"
    done | parallel -j $(nproc) process_region_by_geo {}
}

organize_files()
{
    echo >&2 "Moving files from $WORK_DIR to individual sub-directories..."
    mkdir $WORK_DIR/{region_pair.by_geo,region_pair.by_geo.distribution}
    mv "$WORK_DIR"/routes.*.by_geo{,.logical,.physical} "$WORK_DIR"/region_pair.by_geo/
    mv "$WORK_DIR"/routes.*.by_geo.distribution "$WORK_DIR"/region_pair.by_geo.distribution/
    if [ $GENERATE_ISO_FILES -ne 0 ]; then
        mkdir $WORK_DIR/{region_pair.by_iso,region_pair.by_iso.distribution}
        mv "$WORK_DIR"/routes.*.by_iso "$WORK_DIR"/region_pair.by_iso/
        mv "$WORK_DIR"/routes.*.by_iso.distribution "$WORK_DIR"/region_pair.by_iso.distribution/
    fi

    # Consolidate all the geo distributions TSV files into one, for batch import into SQL
    echo >&2 "Consolidating all the geo distributions TSV files into one, for batch import into SQL..."
    ./combine_per_region_pair_tsvs.py -i "$WORK_DIR"/region_pair.by_geo.distribution/routes.*.by_geo.distribution -o "$WORK_DIR"/routes.all.by_geo.distribution.tsv
    chmod 440 "$WORK_DIR"/routes.all.by_geo.distribution.tsv
    # import this later into SQL.
}

main()
{
    ip_to_geo
    process_raw_geo_data
    organize_files
}

set -e

main
