"""
Dutch Railway Data - Streaming Analysis
边下载边分析：用 streaming file handle 让 pandas 实时解析
"""
import requests, time, gzip, io, os
import pandas as pd

BASE = "https://blobs.duckdb.org/nl-railway"
YEAR = 2024
URL = f"{BASE}/services-{YEAR}.csv.gz"
OUT = os.path.join(os.path.dirname(__file__), f"services-{YEAR}.csv.gz")

print(f"URL: {URL}")
print(f"目标: 边下载边分析\n")

# Step 1: 获取文件大小
t0 = time.time()
r_head = requests.head(URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
total_sz = int(r_head.headers.get("Content-Length", 0))
r_head.close()
print(f"文件总大小: {total_sz/1e6:.0f} MB")
if total_sz:
    print(f"预计下载时间: {total_sz/1024/100/60:.0f} min @ 100KB/s\n")

# Step 2: 分段下载，每 50MB 就分析一次
CHUNK = 50 * 1024 * 1024  # 50MB 一段
buf = b""
downloaded = 0
segment = 0
done = False

print("=" * 60)
print("开始边下载边分析...")
print("=" * 60)

with requests.get(URL, stream=True, timeout=(20, 600), headers={"User-Agent": "Mozilla/5.0"}) as r:
    r.raise_for_status()
    with open(OUT, "wb") as f:
        for chunk in r.iter_content(256 * 1024):
            if chunk:
                f.write(chunk)
                buf += chunk
                downloaded += len(chunk)
                pct = downloaded / total_sz * 100 if total_sz else 0

                # 每达到一个完整 50MB chunk 就分析一次
                while downloaded >= (segment + 1) * CHUNK:
                    segment += 1
                    seg_end = min(segment * CHUNK, downloaded)
                    seg_start = (segment - 1) * CHUNK
                    seg_data = buf[seg_start:seg_end]
                    elapsed = time.time() - t0
                    speed = downloaded / elapsed / 1e3
                    eta = (total_sz - downloaded) / (downloaded / elapsed) / 60 if elapsed > 10 else 0

                    print(f"\n--- Segment {segment}: {downloaded/1e6:.0f}MB ({pct:.0f}%) ---")

                    if seg_data[:2] == b'\x1f\x8b':
                        try:
                            with gzip.open(io.BytesIO(seg_data), "rt") as gf:
                                df = pd.read_csv(gf, nrows=3)
                                print(f"  列名: {list(df.columns)}")
                                print(df.head(2).to_string())
                        except Exception as e:
                            print(f"  (gzip 边界未对齐，跳过: {e})")
                    else:
                        print(f"  (非 gzip 数据段)")

                    print(f"  速度: {speed:.0f} KB/s  ETA: {eta:.0f} min")

    # 下载完成，解析整个文件
    done = True

print(f"\n下载完成！总大小: {downloaded/1e6:.0f} MB")
print(f"总耗时: {(time.time()-t0)/60:.1f} min")

# 完整解析
if done:
    print("\n" + "=" * 60)
    print("完整文件分析...")
    print("=" * 60)
    with gzip.open(OUT, "rt") as gf:
        # 先读 schema
        df_sample = pd.read_csv(gf, nrows=5)
        print(f"列名: {list(df_sample.columns)}")
        print(df_sample.head(3).to_string())

    # 统计行数（流式）
    print("\n行数统计:")
    with gzip.open(OUT, "rt") as gf:
        total_rows = sum(1 for _ in gf) - 1  # 减 header
    print(f"  2024 年总行数: {total_rows:,}")

    # 删除临时文件
    os.remove(OUT)
    print(f"\n临时文件已清理")
