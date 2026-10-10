# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

# Try wider range
for start, end in [
    ('2026-07-20T00:00:00+02:00', '2026-07-27T00:00:00+02:00'),
    ('2026-07-01T00:00:00+02:00', '2026-07-31T00:00:00+02:00'),
]:
    result = call_tool('getScheduledPosts', {
        'blogId': 1,
        'startDate': start,
        'endDate': end
    })
    posts = result if isinstance(result, list) else result.get('posts', result.get('data', []))
    print(f"Range {start[:10]} to {end[:10]}: {len(posts)} posts")
    for p in posts[:4]:
        net = str(p.get('network', '?'))[:6]
        pid = p.get('id', '?')
        dt = str(p.get('scheduledAt', ''))[:16]
        print(f"  ID={pid} net={net} {dt}")
