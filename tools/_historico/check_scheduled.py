# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

result = call_tool('getScheduledPosts', {
    'blogId': 1,
    'startDate': '2026-07-23T00:00:00+02:00',
    'endDate': '2026-07-26T00:00:00+02:00'
})
posts = result if isinstance(result, list) else result.get('posts', result.get('data', []))
print("Total posts Jul 23-25:", len(posts))
for p in posts:
    net = str(p.get('network', '?'))[:6]
    pid = p.get('id', '?')
    dt = str(p.get('scheduledAt', ''))[:16]
    ptype = p.get('postType', '?')
    media = p.get('media', [])
    url = media[0].get('url', '')[:90] if media else '(no media)'
    print(f"  ID={pid} net={net} {dt} type={ptype}")
    print(f"    {url}")
