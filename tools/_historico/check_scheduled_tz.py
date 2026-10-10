# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

BRAND_ID = "6435452"

# Try with timezone Z suffix
result = call_tool('getScheduledPosts', {
    'brandId': BRAND_ID,
    'fromDate': '2026-07-23T00:00:00Z',
    'toDate': '2026-07-26T23:59:59Z',
    'timezone': 'Europe/Madrid'
})

content = result.get('content', [])
text = content[0].get('text', '') if content else str(result)
print("RAW (first 3000):", text[:3000])
