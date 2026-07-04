"""
UserBehavior.csv Analysis
Data lakehouse demo - local data analysis
"""
import pandas as pd, time

PATH = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\data\raw\UserBehavior.csv"

print("=" * 60)
print("Step 1: Schema + 前 5 行")
print("=" * 60)
t0 = time.time()
df_sample = pd.read_csv(PATH, nrows=5)
print(f"耗时: {time.time()-t0:.1f}s")
print(f"列名: {list(df_sample.columns)}")
print(f"类型:\n{df_sample.dtypes}")
print(f"\n样本:\n{df_sample.to_string()}")

print("\n" + "=" * 60)
print("Step 2: 基本统计")
print("=" * 60)
t0 = time.time()
df = pd.read_csv(PATH)
print(f"耗时: {time.time()-t0:.1f}s")
print(f"总行数: {len(df):,}")
print(f"内存: {df.memory_usage(deep=True).sum()/1e6:.1f} MB")
print(f"\n列统计:\n{df.describe(include='all').to_string()}")

# 数值列分布
numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
print(f"\n数值列: {numeric_cols}")

print("\n" + "=" * 60)
print("Step 3: 用户行为分析")
print("=" * 60)

# 用户数
if "user_id" in df.columns:
    print(f"唯一用户数: {df['user_id'].nunique():,}")

# 商品数
if "item_id" in df.columns:
    print(f"唯一商品数: {df['item_id'].nunique():,}")

# 类别数
if "category_id" in df.columns:
    print(f"唯一类别数: {df['category_id'].nunique():,}")

# 行为类型
if "behavior_type" in df.columns:
    print(f"\n行为类型分布:")
    print(df["behavior_type"].value_counts())

# 时间范围
date_col = None
for col in ["date", "time", "timestamp", "datetime"]:
    if col in df.columns:
        date_col = col
        break

if date_col:
    print(f"\n时间范围: {df[date_col].min()} ~ {df[date_col].max()}")

print("\n" + "=" * 60)
print("分析完成！")
print("=" * 60)
