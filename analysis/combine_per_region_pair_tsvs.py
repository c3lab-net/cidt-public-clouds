#!/usr/bin/env python3

import logging
import os
import sys
from typing import Optional
import pandas as pd
import argparse

from common import init_logging, detect_cloud_regions_from_filename

REQUIRED_COLUMNS = ['count', 'hop_count', 'distance_km', 'route']

def combine_tsv_files_and_add_regions(input_files: list[str], output_file: str,
                                      columns_to_add: Optional[dict[str, str]]) -> None:
    """Combine the TSV files into a single TSV file with added src/dst region information based on the file name."""
    combined_df = pd.DataFrame()
    for input_file in input_files:
        logging.info(f'Processing {input_file} ...')
        cloud_regions = detect_cloud_regions_from_filename(os.path.basename(input_file))
        assert cloud_regions is not None, f"Cannot detect cloud regions from filename '{input_file}'"
        (src_cloud, src_region, dst_cloud, dst_region) = cloud_regions

        df = pd.read_csv(input_file, delimiter='\t')
        for column in REQUIRED_COLUMNS:
            assert column in df.columns, f"Required column '{column}' is missing in '{input_file}'"

        df['src_cloud'] = src_cloud
        df['src_region'] = src_region
        df['dst_cloud'] = dst_cloud
        df['dst_region'] = dst_region

        if columns_to_add:
            for column, value in columns_to_add.items():
                assert column not in df.columns, f"Column '{column}' already exists in '{input_file}'"
                df[column] = value

        combined_df = pd.concat([combined_df, df], ignore_index=True)

    # Reorder columns with the new ones and required columns at the beginning
    FILE_NAME_COLUMNS = ['src_cloud', 'src_region', 'dst_cloud', 'dst_region']
    per_file_columns = combined_df.columns.tolist()
    for required_column in FILE_NAME_COLUMNS + REQUIRED_COLUMNS:
        per_file_columns.remove(required_column)
    new_columns = FILE_NAME_COLUMNS + REQUIRED_COLUMNS + per_file_columns
    combined_df = combined_df[new_columns]

    logging.info(f'Writing to {output_file} ...')
    combined_df.to_csv(output_file if output_file else sys.stdout, sep='\t', index=False)

def parse_args():
    parser = argparse.ArgumentParser(description='Process TSV files and add columns.')
    parser.add_argument('-i', '--input-tsvs', type=str, required=True, nargs='+', help='The TSV files for each region, must be named in the format of *.src_cloud.src_region.dst_cloud.dst_region.*')
    parser.add_argument('-o', '--output-tsv', type=str, help='The output TSV file.')
    parser.add_argument('-a', '--add', type=str, nargs='+', help='The [column=value] to add to the output TSV file.')
    args = parser.parse_args()

    if args.add:
        for key_value_pair in args.add:
            DELIMITER = '='
            assert DELIMITER in key_value_pair, f'Invalid --add value: {key_value_pair}'
            (column, value) = key_value_pair.split(DELIMITER, maxsplit=1)
            args.columns_to_add = {}
            args.columns_to_add[column] = value
    else:
        args.columns_to_add = None

    return args

def main():
    init_logging()
    args = parse_args()
    combine_tsv_files_and_add_regions(args.input_tsvs, args.output_tsv, args.columns_to_add)

if __name__ == '__main__':
    main()
