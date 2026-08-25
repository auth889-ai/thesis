#!/bin/bash
# Arm: rtdetr_r50vd fine-tune from the official COCO+Objects365 checkpoint.
export ARCH_CFG=rtdetr_r50vd_6x_coco.yml
export OFFICIAL_CKPT_URL=https://github.com/lyuwenyu/storage/releases/download/v0.1/rtdetr_r50vd_2x_coco_objects365_from_paddle.pth
aws s3 cp s3://dhakaflow-train-915644996102/code/rtdetr_poribohon_common.sh /tmp/common.sh
bash /tmp/common.sh
