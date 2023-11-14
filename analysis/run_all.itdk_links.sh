#!/bin/bash

# This script runs all the itdk_link.py commands for the pairs of regions we're interested in.
#   Adjust the parameters below and parallelize the for loops as needed.

# Regions we're interested in
export AWS_REGIONS="eu-central-1 eu-north-1 eu-south-1 eu-west-1 eu-west-2 eu-west-3 ca-central-1 us-east-1 us-east-2 us-west-1 us-west-2 sa-east-1 af-south-1 ap-northeast-1 ap-northeast-2 ap-northeast-3 ap-south-1 ap-southeast-1 ap-southeast-2"
export GCP_REGIONS="europe-central2 europe-north1 europe-west1 europe-west2 europe-west3 europe-west4 europe-west6 northamerica-northeast1 northamerica-northeast2 southamerica-east1 southamerica-west1 us-central1 us-central2 us-east1 us-east4 us-east7 us-west1 us-west2 us-west3 us-west4 asia-east1 asia-northeast1 asia-northeast2 asia-northeast3 asia-south1 asia-south2 asia-southeast1 australia-southeast1 australia-southeast2"
# export SRC_REGION="TBD"
export HOSTNAME="$(hostname -s)"

# Note: these are meant to be run over multiple console windows and over multiple machines.
#   Remove the tee redirects if you want to run them in the background.
#   Use other batch execution systems if you want to automatically run them on multiple machines.

# From AWS
for SRC_REGION in $(echo $AWS_REGIONS); do
	NUMANODE=0 && numactl --cpunodebind=$NUMANODE --membind=$NUMANODE /usr/bin/time -v ./itdk_links.py --src-cloud gcloud --src-regions $SRC_REGION --dst-cloud aws --dst-regions $(echo "$AWS_REGIONS") 1> >(tee $HOSTNAME.numa$NUMANODE.routes.aws.$SRC_REGION.aws.all.by_ip) 2> >(tee $HOSTNAME.numa$NUMANODE.routes.aws.$SRC_REGION.aws.all.err >&2)
	NUMANODE=1 && numactl --cpunodebind=$NUMANODE --membind=$NUMANODE /usr/bin/time -v ./itdk_links.py --src-cloud gcloud --src-regions $SRC_REGION --dst-cloud gcloud --dst-regions $(echo "$GCP_REGIONS") 1> >(tee $HOSTNAME.numa$NUMANODE.routes.aws.$SRC_REGION.gcloud.all.by_ip) 2> >(tee $HOSTNAME.numa$NUMANODE.routes.aws.$SRC_REGION.gcloud.all.err >&2)
done

# From gcloud
for SRC_REGION in $(echo $GCP_REGIONS); do
	NUMANODE=0 && numactl --cpunodebind=$NUMANODE --membind=$NUMANODE /usr/bin/time -v ./itdk_links.py --src-cloud gcloud --src-regions $SRC_REGION --dst-cloud aws --dst-regions $(echo "$AWS_REGIONS") 1> >(tee $HOSTNAME.numa$NUMANODE.routes.gcloud.$SRC_REGION.aws.all.by_ip) 2> >(tee $HOSTNAME.numa$NUMANODE.routes.gcloud.$SRC_REGION.aws.all.err >&2)
	NUMANODE=1 && numactl --cpunodebind=$NUMANODE --membind=$NUMANODE /usr/bin/time -v ./itdk_links.py --src-cloud gcloud --src-regions $SRC_REGION --dst-cloud gcloud --dst-regions $(echo "$GCP_REGIONS") 1> >(tee $HOSTNAME.numa$NUMANODE.routes.gcloud.$SRC_REGION.gcloud.all.by_ip) 2> >(tee $HOSTNAME.numa$NUMANODE.routes.gcloud.$SRC_REGION.gcloud.all.err >&2)
done
