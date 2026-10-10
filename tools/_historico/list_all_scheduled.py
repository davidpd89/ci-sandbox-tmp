# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

BRAND_ID = "6435452"

result = call_tool('getScheduledPosts', {
    'brandId': BRAND_ID,
    'fromDate': '2026-07-23T00:00:00Z',
    'toDate': '2026-07-26T23:59:59Z',
    'timezone': 'Europe/Madrid'
})

content = result.get('content', [])
text = content[0].get('text', '') if content else str(result)
try:
    data = json.loads(text)
    posts = data.get('data', [])
    print(f"Total posts Jul 23-26: {len(posts)}\n")
    for p in posts:
        pid = p.get('id', '?')
        uuid = p.get('uuid', '?')
        dt = p.get('publicationDate', {}).get('dateTime', '?')
        nets = [pr.get('network', '?') for pr in p.get('providers', [])]
        media = p.get('media', [])
        url = media[0][:80] if media else '(no media)'
        txt = p.get('text', '')[:60]
        print(f"  ID={pid}")
        print(f"  uuid={uuid}")
        print(f"  date={dt}  nets={nets}")
        print(f"  media: {url}")
        print(f"  text: {txt}")
        print()
except Exception as e:
    print(f"Error: {e}")
    print(text[:500])
