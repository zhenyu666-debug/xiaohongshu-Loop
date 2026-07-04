"""
Dutch Railway Data Downloader
Source: https://blobs.duckdb.org/nl-railway/
7 files, ~2.51 GB total compressed
"""
import requests
import os
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT_DIR = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\duckdb_railway"
os.makedirs(OUT_DIR, exist_ok=True)

FILES = [
    ("services-2019.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2019.csv.gz", 348_000_000),
    ("services-2020.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2020.csv.gz", 355_000_000),
    ("services-2021.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2021.csv.gz", 350_000_000),
    ("services-2022.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2022.csv.gz", 356_000_000),
    ("services-2023.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2023.csv.gz", 346_000_000),
    ("services-2024.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2024.csv.gz", 357_000_000),
    ("services-2025.csv.gz", "https://blobs.duckdb.org/nl-railway/services-2025.csv.gz", 396_000_000),
]

total_expected = sum(f[2] for f in FILES)
done_count = [0]
total_downloaded = [0]
start_time = time.time()

def fmt_size(b):
    if b >= 1e9: return f"{b/1e9:.2f}GB"
    return f"{b/1e6:.0f}MB"

def download_one(name, url, expected):
    path = os.path.join(OUT_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) >= expected * 0.9:
        sz = os.path.getsize(path)
        done_count[0] += 1
        total_downloaded[0] += sz
        print(f"SKIP  {name} ({fmt_size(sz)} already exists)")
        return True, name, sz

    print(f"DOWN  {name} ...")
    sys.stdout.flush()

    try:
        t0 = time.time()
        r = requests.get(url, stream=True, timeout=(30, 300),
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        total_sz = int(r.headers.get("Content-Length", 0))

        downloaded = 0
        chunk_size = 1024 * 512  # 512KB chunks
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    # Progress every 10MB
                    if downloaded % (10 * 1024 * 1024) < chunk_size:
                        pct = downloaded / total_sz * 100 if total_sz else 0
                        elapsed = time.time() - t0
                        speed = downloaded / elapsed / 1e6 if elapsed > 0 else 0
                        eta = (total_sz - downloaded) / (downloaded / elapsed) if elapsed > 0 and downloaded > 0 else 0
                        bar = "#" * int(pct / 5)
                        sys.stdout.write(
                            f"\r      {name}  {pct:5.1f}%  {fmt_size(downloaded)}/{fmt_size(total_sz)}"
                            f"  {speed:.0f}MB/s  eta={eta:.0f}s{'':20s}\r"
                        )
                        sys.stdout.flush()

        elapsed = time.time() - t0
        final_sz = os.path.getsize(path)
        done_count[0] += 1
        total_downloaded[0] += final_sz

        avg_speed = final_sz / elapsed / 1e6
        total_elapsed = time.time() - start_time
        avg_total = total_downloaded[0] / total_elapsed
        remaining = total_expected - total_downloaded[0]
        eta_total = remaining / avg_total / 60 if avg_total > 0 else 0

        print(f"\nOK    [{done_count[0]}/{len(FILES)}] {name}"
              f"  {fmt_size(final_sz)}  {avg_speed:.0f}MB/s"
              f"  total={fmt_size(total_downloaded[0])}"
              f"  eta={eta_total:.0f}min")
        return True, name, final_sz

    except Exception as e:
        print(f"\nFAIL  {name}: {type(e).__name__} {e}")
        return False, name, 0


print(f"Target: {OUT_DIR}")
print(f"Files: {len(FILES)}  Expected: {fmt_size(total_expected)}")
print("=" * 70)

# Count existing
for name, url, expected in FILES:
    path = os.path.join(OUT_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) >= expected * 0.9:
        sz = os.path.getsize(path)
        done_count[0] += 1
        total_downloaded[0] += sz

if done_count[0] == len(FILES):
    print(f"All {len(FILES)} files already exist!")
else:
    print(f"Already have {done_count[0]} files, need to download {len(FILES) - done_count[0]}\n")

with ThreadPoolExecutor(max_workers=1) as pool:
    futures = {
        pool.submit(download_one, name, url, expected): (name, url, expected)
        for name, url, expected in FILES
    }
    for fut in as_completed(futures):
        pass  # results already printed inside download_one

elapsed_total = time.time() - start_time
final_total = sum(
    os.path.getsize(os.path.join(OUT_DIR, f[0]))
    for f in FILES if os.path.exists(os.path.join(OUT_DIR, f[0]))
)
print(f"\n{'=' * 70}")
print(f"DONE in {elapsed_total/60:.1f} min")
print(f"Files: {done_count[0]}/{len(FILES)}")
print(f"Total: {fmt_size(final_total)}")
failed = [f[0] for f in FILES if not os.path.exists(os.path.join(OUT_DIR, f[0]))]
if failed:
    print(f"Missing: {failed}")
