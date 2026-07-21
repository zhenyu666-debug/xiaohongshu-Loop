#!/usr/bin/env python3
"""Quick speed test against Cloudflare R2."""
import requests, time

print("Speed test: download first 50 MB of SF10 dataset")
url = "https://datasets.ldbcouncil.org/snb-interactive-v1/social_network-sf10-CsvBasic-LongDateFormatter.tar.zst"

t0 = time.time()
resp = requests.get(url, stream=True, timeout=60)
resp.raise_for_status()

downloaded = 0
target = 50 * 1024 * 1024  # 50 MB
for chunk in resp.iter_content(chunk_size=1024 * 1024):
    downloaded += len(chunk)
    if downloaded >= target:
        break

elapsed = time.time() - t0
rate = downloaded / elapsed / (1024**2)
print(f"Downloaded {downloaded/(1024**2):.1f} MB in {elapsed:.1f}s = {rate:.2f} MB/s")
print(f"Estimated time for full file (2.5 GB): {(2.5 * 1024) / rate / 60:.1f} min")
resp.close()