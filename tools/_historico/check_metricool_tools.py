# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import list_tools, call_tool
import json

tools = list_tools()
print(f"Total tools: {len(tools)}")
for t in tools:
    name = t['name']
    desc = t.get('description', '')[:60]
    schema = t.get('inputSchema', {})
    props = list(schema.get('properties', {}).keys())
    print(f"\n  {name}")
    print(f"    desc: {desc}")
    print(f"    params: {props}")
