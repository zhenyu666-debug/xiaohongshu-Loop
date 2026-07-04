"""
NYC Yellow Taxi Data 全量下载器 (2019-2024)
来源: AWS CloudFront - 无需认证直链
"""
import urllib.request
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year}-{month:02d}.parquet"
OUT_DIR = Path(r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\nyc_taxi")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 2019-01 到 2024-07 所有可用文件
urls = []
for y in range(2019, 2025):
    for m in range(1, 13):
        if y == 2024 and m > 7:
            break
        url = BASE_URL.format(year=y, month=m)
        out_file = OUT_DIR / f"yellow_tripdata_{y}-{m:02d}.parquet"
        urls.append((url, out_file))

total_expected_gb = 3.74
completed = 0
total_downloaded_gb = 0.0
failed = []

def download_one(url_file):
    url, out_file = url_file
    if out_file.exists() and out_file.stat().st_size > 1000:
        return True, out_file, 0  # already exists, skip
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        out_file.write_bytes(data)
        return True, out_file, len(data)
    except Exception as e:
        return False, out_file, 0

start = time.time()
total_sz = sum(u[1].stat().st_size for u in urls if u[1].exists()) / 1e9
print(f"已有本地文件: {total_sz:.2f} GB")
print(f"还需下载: {len(urls) - sum(1 for u in urls if u[1].exists())} 个文件")
print(f"预计总大小: {total_expected_gb:.2f} GB")
print(f"并发数: 8\n{'─'*60}")

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(download_one, u): u for u in urls}

    for fut in as_completed(futures):
        ok, out_file, sz = fut.result()
        completed += 1
        if ok:
            elapsed = time.time() - start
            total_downloaded_gb = sum(
                f.stat().st_size for f in OUT_DIR.glob("*.parquet")
            ) / 1e9
            speed = total_downloaded_gb / elapsed * 3600 if elapsed > 0 else 0
            eta = (total_expected_gb - total_downloaded_gb) / (speed/3600) if speed > 0 else 0
            print(f"[{completed}/{len(urls)}] {out_file.name}  "
                  f"total={total_downloaded_gb:.2f}GB  speed={speed:.1f}GB/h  eta={eta:.0f}s")
        else:
            failed.append(out_file.name)
            print(f"[{completed}/{len(urls)}] FAILED {out_file.name}")

elapsed = time.time() - start
final_gb = sum(f.stat().st_size for f in OUT_DIR.glob("*.parquet")) / 1e9
print(f"\n{'═'*60}")
print(f"完成! 用时 {elapsed/60:.1f} min")
print(f"文件数: {len(list(OUT_DIR.glob('*.parquet')))} / {len(urls)}")
print(f"总大小: {final_gb:.2f} GB")
if failed:
    print(f"失败: {failed}")
