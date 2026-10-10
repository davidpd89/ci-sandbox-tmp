# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

# Get brand settings
brands = call_tool('getBrandSettings', {})
print("Brands raw:", str(brands)[:600])
