"""What a LargeST instance runs: fetch inputs and any saved state, train PatchSTG through the switch with a state
upload after every epoch, watch for a hang, upload the result, shut down. Filled by `scripts.render`."""
SCRIPT = r"""#!/bin/bash
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
set -x
NAME=@NAME@; BUCKET=@BUCKET@; SHA=@SHA@; RG=@REGION@; LRG=@LREGION@; EPOCHS=@EPOCHS@
H=/home/ec2-user; S3=s3://$BUCKET/jobs/$NAME; TLOG=/tmp/PatchSTG_$RG.log; STATE=$H/state/${LRG}_state.pt
TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 600")
IID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
echo 1 > /proc/sys/kernel/sysrq
( sleep $((@MAXH@ * 3600)); shutdown -h now ) &          # hard cap
cat > $H/fail.sh <<'FAIL'
#!/bin/bash
# stop the job, leave a record, power off (kernel power-off if shutdown itself stalls)
pkill -9 -f patchstg_official.py
printf '{"job": "%s", "instance": "%s", "event": "FAILED", "reason": "%s", "utc": "%s"}\n' "$NAME" "$IID" "$1" "$(date -u +%FT%TZ)" > /tmp/FAILED.json
( sleep 120; echo o > /proc/sysrq-trigger ) &
aws s3 cp /tmp/FAILED.json $S3/FAILED.json
aws s3 cp $TLOG $S3/logs/PatchSTG_${RG}_$IID.log; aws s3 cp $TLOG.mem $S3/logs/memory_$IID.log; aws s3 cp /var/log/dhakaflow.log $S3/logs/machine_$IID.log
shutdown -h now
FAIL
cat > $H/epoch.sh <<'EPOCH'
#!/bin/bash
aws s3 cp $STATE $S3/state/ --only-show-errors && aws s3 cp $STATE.best $S3/state/ --only-show-errors
aws s3 cp $TLOG $S3/logs/PatchSTG_${RG}_$IID.log --only-show-errors; aws s3 cp $TLOG.mem $S3/logs/memory_$IID.log --only-show-errors
EPOCH
cat > $H/watchdog.sh <<'WATCH'
@WATCHDOG@
WATCH
chmod +x $H/fail.sh $H/epoch.sh $H/watchdog.sh
export NAME IID S3 TLOG STATE RG
touch $TLOG && nohup $H/watchdog.sh $TLOG 1800 60 $H/fail.sh >/dev/null 2>&1 &
( while true; do sleep 60; aws s3 cp /var/log/dhakaflow.log $S3/logs/live.log >/dev/null 2>&1; done ) &
aws s3 cp $S3/in/ $H/in/ --recursive || true
aws s3 cp $S3/state/ $H/state/ --recursive || true        # a previous instance's epochs, if it was interrupted
cd $H
git clone -q https://github.com/LMissher/PatchSTG.git patchstg && cd patchstg && git checkout -q $SHA
PY=""
for C in /opt/pytorch/bin/python /opt/conda/envs/pytorch/bin/python /opt/conda/bin/python \
         /usr/local/bin/python3 /usr/bin/python3 $(ls -d /opt/*/bin/python /opt/*/*/bin/python 2>/dev/null); do
  if [ -x "$C" ] && "$C" -c "import torch" >/dev/null 2>&1; then PY="$C"; break; fi
done
if [ -z "$PY" ]; then $H/fail.sh "SETUP: no python with torch on this image"; exit 1; fi
$PY -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0))"
$PY -m pip install -q timm scikit-learn pandas
mkdir -p data/$RG cpt log && cp $H/in/flow$LRG.npz data/$RG/ && cp $H/in/adj.npy data/$RG/ 2>/dev/null || true
W=$H/df/core/ml/forecasting/training                                 # the switch finds results/ four levels up
mkdir -p $W $H/.dhakaflow/upstream && cp $H/in/patchstg_official.py $H/in/patchstg_resume.py $W/
ln -sfn $H/patchstg $H/.dhakaflow/upstream/PatchSTG
EP=""; [ "$EPOCHS" != "0" ] && EP="--epochs $EPOCHS"
echo "=== TRAIN PatchSTG $RG on $IID (authors' Solver, 4 loader workers, state after every epoch) ==="
HOME=$H timeout $((@MAXH@ * 3600 - 1800)) $PY $W/patchstg_official.py --region $RG --mode train --device cuda --workers 4 \
  --resume $STATE --on-epoch $H/epoch.sh $EP 2>&1 | tee -a $TLOG
RC=${PIPESTATUS[0]}
if [ "$RC" != "0" ]; then $H/fail.sh "EXIT: training ended with code $RC (124 = the time cap)"; exit 1; fi   # no DONE marker for a failed job
$H/epoch.sh
aws s3 cp cpt/${LRG}_model $S3/checkpoints/PatchSTG/$RG/${LRG}_model
aws s3 cp /var/log/dhakaflow.log $S3/logs/machine_$IID.log
echo DONE > /tmp/DONE && aws s3 cp /tmp/DONE $S3/DONE
shutdown -h now
"""
