#!/bin/bash
# P1 arm: RT-DETR fine-tune on Poribohon-BD (official pipeline, pinned SHA).
# Sourced by per-arm wrappers that set: ARCH_CFG, OFFICIAL_CKPT_URL.
# Runs inside the AWS spot instance under scripts/aws/launch_arm.py user-data:
#   $ARM_NAME and $S3_BASE are exported; /workspace/ckpt + /workspace/logs are
#   synced to S3 every 5 min; exit code lands in logs/<arm>/EXIT_CODE.
set -exo pipefail
cd /workspace
S3=s3://dhakaflow-train-915644996102

dnf install -y -q git python3.11 python3.11-pip
aws s3 cp $S3/code/p1_code.tar.gz . && tar xzf p1_code.tar.gz
aws s3 cp $S3/datasets/pori_yolo.tar.gz . && tar xzf pori_yolo.tar.gz

python3.11 -m venv venv && . venv/bin/activate
pip -q install --upgrade pip
# Authors pin torch==2.0.1 / torchvision==0.15.2 (requirements.txt @ 068dfde).
pip -q install torch==2.0.1 torchvision==0.15.2 \
    --index-url https://download.pytorch.org/whl/cu118
pip -q install pycocotools PyYAML scipy transformers pillow

# Official repo at the pinned SHA — never modified.
git clone https://github.com/lyuwenyu/RT-DETR.git
git -C RT-DETR checkout 068dfde65f2667ad6555883c69d73de886518cad

# Format adapter: YOLO layout -> COCO instances JSON (translation only).
python - <<'PYEOF'
import sys, pathlib
sys.path.insert(0, "/workspace")
from research.perception.voc_to_yolo import PORIBOHON_CLASSES
from research.perception.yolo_to_coco import convert_split
root = pathlib.Path("/workspace/pori_yolo")
for split in ("train", "val", "test"):
    s = convert_split(root/"images"/split, root/"labels_split"/split,
                      PORIBOHON_CLASSES,
                      pathlib.Path(f"/workspace/coco/instances_{split}.json"))
    print(split, s)
PYEOF

curl -sL -o /workspace/official_ckpt.pth "$OFFICIAL_CKPT_URL"

# Fine-tune config: include the official arch config, override ONLY dataset,
# class count, epochs (fair predeclared budget: 24 for every arm), output dir.
cat > RT-DETR/rtdetr_pytorch/configs/rtdetr/${ARM_NAME}.yml <<CFGEOF
__include__: ['./${ARCH_CFG}', ]

output_dir: /workspace/ckpt/out
epoches: 24
num_classes: 15
remap_mscoco_category: False

train_dataloader:
  dataset:
    img_folder: /workspace/pori_yolo/images/train/
    ann_file: /workspace/coco/instances_train.json

val_dataloader:
  dataset:
    img_folder: /workspace/pori_yolo/images/val/
    ann_file: /workspace/coco/instances_val.json
CFGEOF

mkdir -p /workspace/ckpt /workspace/logs
cd RT-DETR/rtdetr_pytorch

# Resume if a previous spot life left a checkpoint on S3.
RESUME=""
if aws s3 cp $S3/ckpt/$ARM_NAME/out/checkpoint.pth /workspace/ckpt/out/checkpoint.pth 2>/dev/null; then
  RESUME="-r /workspace/ckpt/out/checkpoint.pth"
  echo "resuming from synced checkpoint"
fi

python tools/train.py -c configs/rtdetr/${ARM_NAME}.yml \
  $( [ -z "$RESUME" ] && echo "-t /workspace/official_ckpt.pth" ) \
  $RESUME --amp --seed 42 2>&1 | tee /workspace/logs/train.log

# Test-split evaluation with the trained weights.
sed -i 's#instances_val#instances_test#; s#images/val/#images/test/#' \
  configs/rtdetr/${ARM_NAME}.yml
python tools/train.py -c configs/rtdetr/${ARM_NAME}.yml \
  -r /workspace/ckpt/out/checkpoint.pth --test-only \
  2>&1 | tee /workspace/logs/test_eval.log
