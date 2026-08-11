#!/usr/bin/env python3
import json, shutil, subprocess, sys
checks={}
for b in ['sumo','netconvert']:
    p=shutil.which(b); checks[b]=p
    if p:
        checks[b+'_version']=subprocess.run([b,'--version'],capture_output=True,text=True).stdout.splitlines()[:2]
try:
    import traci; checks['traci']=traci.__file__
except Exception as e: checks['traci_error']=repr(e)
print(json.dumps(checks,indent=2))
if not checks.get('sumo') or not checks.get('netconvert'): sys.exit(2)
