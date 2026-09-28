#!/bin/bash
export MODEL=GWNet
aws s3 cp s3://dhakaflow-train-915644996102/code/p3_basicts_common.sh /tmp/p3_common.sh
bash /tmp/p3_common.sh
