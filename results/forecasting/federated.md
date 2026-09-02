# Federated forecasting under a SIMULATED V2X link

The one experiment where the forecasting half and the networking half of this project produce a single table: prediction accuracy and communication cost measured together, on the same run.

METR-LA, 207 real loop detectors partitioned into RSU clients; 30 FedAvg rounds x 1 local epoch; horizon 12 steps. Trained on AWS (A10G), never locally.

**The link is SIMULATED.** Its delivery ratio (0.975) and latency come from 6,548,621 ITS-G5 messages in 5 Eclipse MOSAIC runs on the Dhaka R1 network. MOSAIC is an official simulator; these are simulated communication events, not measurements on radio hardware.

| clients | arm | MAE | vs centralized | uplink | rounds | updates lost | link time s |
|---|---|---|---|---|---|---|---|
| 4 | centralized | 4.9755 | +0.0 % | 0.0 MB | 0 | 0 | 0.0 |
| 4 | local_only | 4.9895 | +0.3 % | 0.0 MB | 0 | 0 | 0.0 |
| 4 | federated | 4.9819 | +0.1 % | 1.8 MB | 30 | 0 | 0.0 |
| 4 | federated_v2x | 4.9795 | +0.1 % | 1.8 MB | 30 | 2 | 3.4 |
| 8 | centralized | 4.9755 | +0.0 % | 0.0 MB | 0 | 0 | 0.0 |
| 8 | local_only | 4.9863 | +0.2 % | 0.0 MB | 0 | 0 | 0.0 |
| 8 | federated | 4.9903 | +0.3 % | 3.6 MB | 30 | 0 | 0.0 |
| 8 | federated_v2x | 4.9826 | +0.1 % | 3.6 MB | 30 | 6 | 6.88 |
| 16 | centralized | 4.9755 | +0.0 % | 0.0 MB | 0 | 0 | 0.0 |
| 16 | local_only | 4.9942 | +0.4 % | 0.0 MB | 0 | 0 | 0.0 |
| 16 | federated | 5.0048 | +0.6 % | 7.2 MB | 30 | 0 | 0.0 |
| 16 | federated_v2x | 5.0032 | +0.6 % | 7.2 MB | 30 | 12 | 13.94 |

## What this answers

**The simulated V2X link costs essentially nothing in accuracy.** At every client count the impaired arm matches the perfect-link arm to within 0.01 MAE — at 16 clients, losing 12 of 480 updates moved MAE by -0.0016, which is inside run-to-run noise. At an ITS-G5 delivery ratio of 0.975, FedAvg simply absorbs the loss.

**What does cost accuracy is partitioning, not the link.** Federating at all costs +0.1 % at 4 clients and +0.6 % at 16: the more the sensor graph is split, the worse the forecast. Uplink volume meanwhile scales linearly with clients (1.8 -> 3.6 -> 7.2 MB), so the trade is between communication cost and accuracy, and the network impairment is a side issue at these delivery ratios.

**Caveat on the absolute numbers.** These MAEs (~5.0) are from a small model run for 30 rounds to isolate the communication question. They are not competitive with the tuned benchmark architectures (Graph WaveNet reaches 2.72 on the same data) and must not be compared with them. What is meaningful here is the difference BETWEEN the arms, which share everything except the link and the partition.

Raw run logs: `federated_logs/`. Machine-readable: `federated.json`.

Regenerate: `python pipeline/forecasting/aws_train.py --job federated-v2x --federated`.
