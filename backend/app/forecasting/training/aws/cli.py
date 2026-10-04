"""The command line: plan / launch / status / collect / terminate a benchmark job, or launch and
collect a city-dataset job."""
from __future__ import annotations

import argparse

from . import benchmark
from .city import city_collect, city_launch
from .largest import largest_collect, largest_launch
from .settings import JOB


def parser(doc: str = "") -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--plan", action="store_true")
    p.add_argument("--launch", action="store_true")
    p.add_argument("--status", action="store_true")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--collect-checkpoints", action="store_true", help="download trained .pt artefacts")
    p.add_argument("--terminate", action="store_true")
    p.add_argument("--finish", action="store_true", help="after DONE: collect the row and checkpoint, score Protocol B and conformal")
    p.add_argument("--models", default="STID,GWNet")
    p.add_argument("--datasets", default="METR-LA")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--largest", default="", help="LargeST region (SD/GBA/GLA/CA): train PatchSTG with the authors' main.py; --launch / --collect")
    p.add_argument("--instance-type", default="g5.xlarge,g5.2xlarge",
                   help="ladder of single-GPU types; g5 (A10G) is the verified CUDA path, add g6.xlarge only after verifying L4")
    p.add_argument("--max-hours", type=int, default=4)
    p.add_argument("--opencity", action="store_true", help="cross-city evaluation with the official OpenCity foundation model")
    p.add_argument("--oc-batch", type=int, default=8, help="OpenCity eval batch size; cities with many nodes (TrafficSH has 896 vs PEMS07M's 228) need 1-2 to fit a 22 GB A10G")
    p.add_argument("--cities", default="PEMS07M,TrafficSH,TrafficNJ,TrafficTJ",
                   help="OpenCity datasets to evaluate — HELD-OUT cities only; METR_LA and PEMS_BAY are in its pre-training corpus and are not zero-shot")
    p.add_argument("--federated", action="store_true", help="run the federated-over-measured-V2X experiment instead of the baselines")
    p.add_argument("--clients", default="4,8,16", help="RSU counts to sweep (federated)")
    p.add_argument("--rounds", type=int, default=30, help="FedAvg rounds (federated)")
    p.add_argument("--job", default="", help="job name (default per-dataset isolation)")
    p.add_argument("--no-spot", action="store_true", help="skip spot entirely; use for runs that must complete without interruption")
    p.add_argument("--allow-on-demand", action="store_true", help="fall back to on-demand (~2x spot) when no spot capacity exists anywhere")
    p.add_argument("--instance-profile", default="dhakaflow-train-profile", help="IAM instance profile granting S3 access")
    p.add_argument("--city-dataset", default="", help="train on an app dataset (user:<id> / live:<city>) instead of a benchmark")
    p.add_argument("--collect-city", default="", help="collect a finished city job by name and write the app's cards")
    return p


def main(doc: str = "") -> int:
    a = parser(doc).parse_args()
    job = a.job or JOB
    if a.collect_city:
        return 0 if city_collect(a.collect_city) else 1
    if a.city_dataset and a.launch:
        return city_launch(a)
    if a.largest:
        a.epochs_set = "--epochs" in __import__("sys").argv
        if a.launch:
            return largest_launch(a)
        if a.collect:
            return largest_collect(a)
        job = a.job or f"patchstg-{a.largest.lower()}"
    for flag, fn in (("plan", benchmark.plan), ("launch", benchmark.launch), ("status", benchmark.status),
                     ("collect", benchmark.collect), ("collect_checkpoints", benchmark.collect_checkpoints), ("finish", benchmark.finish), ("terminate", benchmark.terminate)):
        if getattr(a, flag):
            return fn(a, job)
    return benchmark.plan(a, job)
