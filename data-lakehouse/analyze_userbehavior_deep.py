"""
UserBehavior.csv - Deep Analysis
"""
import pandas as pd, time

PATH = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\data\raw\UserBehavior.csv"

t0 = time.time()
df = pd.read_csv(PATH)
print(f"加载完成: {len(df):,} 行  耗时: {time.time()-t0:.1f}s\n")

# 时间转换
df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
df["date"] = df["datetime"].dt.date
df["hour"] = df["datetime"].dt.hour
df["weekday"] = df["datetime"].dt.day_name()

print("=" * 60)
print("Step 1: 时间范围")
print("=" * 60)
print(f"日期范围: {df['date'].min()} ~ {df['date'].max()}")
print(f"总天数: {(df['date'].max() - df['date'].min()).days + 1} 天")

print("\n" + "=" * 60)
print("Step 2: 按日统计")
print("=" * 60)
daily = df.groupby("date").size()
print(daily.to_string())

print("\n" + "=" * 60)
print("Step 3: 按小时统计（整体）")
print("=" * 60)
hourly = df.groupby("hour").size()
print(hourly.to_string())

print("\n" + "=" * 60)
print("Step 4: 行为漏斗（浏览→收藏→加购→购买）")
print("=" * 60)
funnel = df["behavior_type"].value_counts()
total = len(df)
for bt, cnt in funnel.items():
    label = {"pv": "浏览", "fav": "收藏", "cart": "加购", "buy": "购买"}.get(bt, bt)
    print(f"  {label:4s}: {cnt:>8,}  ({cnt/total*100:5.1f}%)")

# 转化率
pv = funnel.get("pv", 1)
buy = funnel.get("buy", 0)
print(f"\n  浏览→购买转化率: {buy/pv*100:.2f}%")
fav = funnel.get("fav", 0)
cart = funnel.get("cart", 0)
print(f"  收藏→购买转化率: {buy/fav*100:.2f}%")

print("\n" + "=" * 60)
print("Step 5: 热门类别 TOP 10（按购买量）")
print("=" * 60)
buy_df = df[df["behavior_type"] == "buy"]
top_cat = buy_df.groupby("category_id").size().sort_values(ascending=False).head(10)
print(top_cat.to_string())

print("\n" + "=" * 60)
print("Step 6: 热门商品 TOP 10（按购买量）")
print("=" * 60)
top_item = buy_df.groupby("item_id").size().sort_values(ascending=False).head(10)
print(top_item.to_string())

print("\n" + "=" * 60)
print("Step 7: 用户活跃度分布")
print("=" * 60)
user_actions = df.groupby("user_id").size()
print(f"  用户数: {len(user_actions):,}")
print(f"  每用户平均行为: {user_actions.mean():.1f}")
print(f"  中位数: {user_actions.median():.0f}")
print(f"  最多: {user_actions.max():,} 条")
print(f"  最少: {user_actions.min():,} 条")

# 用户分群
bricks = [0, 50, 100, 200, 500, 1000]
labels = ["0-50", "51-100", "101-200", "201-500", "501-1000", ">1000"]
user_actions_binned = pd.cut(user_actions, bins=bricks + [float("inf")], labels=labels)
print(f"\n  用户分群:")
print(user_actions_binned.value_counts().sort_index().to_string())

print("\n" + "=" * 60)
print("Step 8: 购买用户 vs 非购买用户")
print("=" * 60)
buyers = set(buy_df["user_id"].unique())
all_users = set(df["user_id"].unique())
print(f"  总用户: {len(all_users):,}")
print(f"  购买用户: {len(buyers):,}")
print(f"  购买率: {len(buyers)/len(all_users)*100:.1f}%")

# 每个购买用户平均购买次数
if len(buyers) > 0:
    buyer_df = df[df["user_id"].isin(buyers)]
    buys_per_buyer = buyer_df[buyer_df["behavior_type"] == "buy"].groupby("user_id").size()
    print(f"  每购买用户平均购买: {buys_per_buyer.mean():.2f} 次")
    print(f"  购买次数分布: {buys_per_buyer.describe().to_string()}")

print("\n" + "=" * 60)
print("分析完成！")
print("=" * 60)
