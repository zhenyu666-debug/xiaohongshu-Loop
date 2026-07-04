import os
charts = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\charts"
files = sorted(os.listdir(charts))
total = 0
for f in files:
    sz = os.path.getsize(os.path.join(charts, f))
    total += sz
    mb = round(sz/1024/1024, 2)
    print(f"{f:<55} {mb:>7} MB")
print(f"\nTotal: {len(files)} charts, {round(total/1024/1024,2)} MB")
