# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

BRAND_ID = 6435452

result = call_tool('getScheduledPosts', {
    'brandId': BRAND_ID,
    'fromDate': '2026-07-23',
    'toDate': '2026-07-26',
    'timezone': 'Europe/Madrid'
})

content = result.get('content', [])
text = content[0].get('text', '') if content else str(result)
try:
    data = json.loads(text)
    posts = data.get('data', data) if isinstance(data, dict) else data
    if isinstance(posts, list):
        print(f"Posts Jul 23-25: {len(posts)}")
        for p in posts:
            net = str(p.get('network', p.get('socialNetwork', '?')))[:8]
            pid = p.get('id', '?')
            dt = str(p.get('scheduledAt', p.get('date', p.get('publishAt', ''))))[:16]
            ptype = p.get('postType', p.get('type', '?'))
            media = p.get('media', p.get('mediaFiles', []))
            url = ''
            if media and isinstance(media, list):
                url = str(media[0].get('url', media[0].get('link', '')))[:80]
            print(f"  ID={pid} net={net} {dt} type={ptype}")
            if url:
                print(f"    {url}")
    else:
        print("Not a list:", str(posts)[:400])
except Exception as e:
    print(f"Parse error: {e}")
    print("Raw:", text[:800])
