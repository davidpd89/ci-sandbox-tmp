# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'tools')
from metricool_client import call_tool
import json

# Try raw response and different blogId
for blog_id in [1, 0, None]:
    try:
        result = call_tool('getScheduledPosts', {
            'blogId': blog_id,
            'startDate': '2026-07-01T00:00:00+00:00',
            'endDate': '2026-08-01T00:00:00+00:00'
        })
        print(f"blogId={blog_id}: type={type(result).__name__} len={len(result) if isinstance(result, list) else 'n/a'}")
        if isinstance(result, dict):
            print("  keys:", list(result.keys())[:10])
            # Print first 500 chars
            print("  preview:", str(result)[:300])
        elif isinstance(result, list) and len(result) > 0:
            print("  first:", str(result[0])[:200])
    except Exception as e:
        print(f"blogId={blog_id}: ERROR {e}")
