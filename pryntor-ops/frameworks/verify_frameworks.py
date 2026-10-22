import importlib.metadata as m
import json, sys, datetime
packages = {'langgraph':['langgraph'], 'crewai':['crewai'], 'microsoft':['agent-framework-core'], 'openhands':['openhands']}
kind = sys.argv[1]
found={p: m.version(p) for p in packages[kind]}
print(json.dumps({'framework':kind,'packages':found,'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_calls':0,'live_agent':False}))
