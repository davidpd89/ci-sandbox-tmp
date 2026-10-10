# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

BRAND_ID = "6435452"

result = call_tool('getScheduledPosts', {
    'brandId': BRAND_ID,
    'fromDate': '2026-07-23',
    'toDate': '2026-07-26',
    'timezone': 'Europe/Madrid'
})

content = result.get('content', [])
text = content[0].get('text', '') if content else str(result)
print("RAW:", text[:1200])
