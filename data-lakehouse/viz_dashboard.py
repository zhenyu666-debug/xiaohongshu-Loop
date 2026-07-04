"""
Data Lakehouse - Visualization Dashboard
Dutch Railway + UserBehavior 数据的 Matplotlib 图表
"""
import matplotlib
matplotlib.use("Agg")  # headless 模式
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import duckdb, os
from matplotlib.gridspec import GridSpec

# ─── 全局样式 ───────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor": "#1a1a2e",
    "axes.facecolor": "#16213e",
    "axes.edgecolor": "#0f3460",
    "axes.labelcolor": "#e0e0e0",
    "xtick.color": "#a0a0a0",
    "ytick.color": "#a0a0a0",
    "text.color": "#e0e0e0",
    "grid.color": "#0f3460",
    "grid.alpha": 0.4,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlecolor": "#ffffff",
    "legend.facecolor": "#16213e",
    "legend.edgecolor": "#0f3460",
    "legend.labelcolor": "#e0e0e0",
    "font.family": "sans-serif",
})
COLORS = {
    "primary": "#00d4ff",
    "secondary": "#7b2fff",
    "accent": "#ff6b6b",
    "success": "#4ecdc4",
    "warning": "#ffd93d",
    "orange": "#ff9f43",
    "pink": "#fd79a8",
    "green": "#00b894",
}
OUT = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\charts"
os.makedirs(OUT, exist_ok=True)

# ═══════════════════════════════════════════════════════════
# SECTION 1: Dutch Railway Visualizations
# ═══════════════════════════════════════════════════════════

BASE_R = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/duckdb_railway"
con_r = duckdb.connect(":memory:")

common_cols = [
    "Service:RDT-ID", "Service:Date", "Service:Type", "Service:Company",
    "Service:Train number", "Service:Completely cancelled", "Service:Partly cancelled",
    "Service:Maximum delay", "Stop:RDT-ID", "Stop:Station code", "Stop:Station name",
    "Stop:Arrival time", "Stop:Arrival delay", "Stop:Arrival cancelled",
    "Stop:Departure time", "Stop:Departure delay", "Stop:Departure cancelled",
]
select_common = "SELECT " + ", ".join([f'"{c}"' for c in common_cols])
for y in range(2019, 2026):
    con_r.execute(
        f"CREATE VIEW v{y} AS {select_common} "
        f"FROM read_csv_auto('{BASE_R}/services-{y}.csv.gz', compression='gzip', header=true)"
    )
UNION_VIEW = " UNION ALL ".join([f"SELECT * FROM v{y}" for y in range(2019, 2026)])

def qr(sql):
    """Query Railway and return DataFrame"""
    return con_r.execute(sql).fetchdf()

# ── 图表 1: 年度延误趋势 + 取消率 (双 Y 轴) ─────────────
print("Chart 1: Yearly delay trend + cancellation rate")
df = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y', "Service:Date") AS year,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival cancelled" = TRUE) * 100.0 / COUNT(*), 2) AS cancel_pct,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 5) * 100.0 / COUNT(*), 2) AS delay_5m_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")

fig, ax1 = plt.subplots(figsize=(12, 6))
x = range(len(df))
ax1.bar(x, df["avg_delay"], color=COLORS["primary"], alpha=0.85, label="Avg Delay (min)", zorder=3)
ax1.set_xlabel("Year")
ax1.set_ylabel("Avg Arrival Delay (min)", color=COLORS["primary"])
ax1.tick_params(axis="y", labelcolor=COLORS["primary"])
ax1.set_xticks(list(x))
ax1.set_xticklabels(df["year"].tolist())
ax1.set_ylim(0, max(df["avg_delay"]) * 1.4)
ax1.grid(axis="y", alpha=0.4)

ax2 = ax1.twinx()
ax2.plot(x, df["cancel_pct"], color=COLORS["accent"], marker="o", linewidth=2.5,
          markersize=8, label="Cancellation Rate (%)")
ax2.plot(x, df["delay_5m_pct"], color=COLORS["warning"], marker="s", linewidth=2.5,
          markersize=8, label="Delay >5min Rate (%)")
ax2.set_ylabel("Rate (%)", color=COLORS["accent"])
ax2.tick_params(axis="y", labelcolor=COLORS["accent"])
ax2.set_ylim(0, max(df["delay_5m_pct"]) * 1.5)

# COVID annotation
covid_idx = list(df["year"]).index("2020")
ax1.annotate("COVID-19", xy=(covid_idx, df.iloc[covid_idx]["avg_delay"]),
             xytext=(covid_idx + 0.5, df.iloc[covid_idx]["avg_delay"] + 0.3),
             arrowprops=dict(arrowstyle="->", color=COLORS["accent"]),
             color=COLORS["accent"], fontsize=10)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)
ax1.set_title("Dutch Railway: Yearly Delay Trend & Cancellation Rate (2019-2025)")
fig.tight_layout()
fig.savefig(f"{OUT}/01_yearly_delay.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/01_yearly_delay.png")

# ── 图表 2: 各铁路公司延误对比 (TOP 10) ─────────────────
print("Chart 2: Company delay comparison")
df = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        "Service:Company" AS company,
        COUNT(*) AS stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 5) * 100.0 / COUNT(*), 2) AS delay_rate
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) > 50000
    ORDER BY avg_delay DESC
    LIMIT 15
""")

# 过滤小公司
df = df[df["stops"] > 100000].head(12)
colors_bar = [COLORS["accent"] if v > 2 else COLORS["primary"] if v > 1
              else COLORS["success"] for v in df["avg_delay"]]

fig, ax = plt.subplots(figsize=(13, 7))
bars = ax.barh(df["company"][::-1], df["avg_delay"][::-1], color=colors_bar[::-1],
               edgecolor="none", height=0.7)
ax.set_xlabel("Average Arrival Delay (minutes)")
ax.set_title("Top Railway Companies by Average Delay (>100K stops)")
ax.axvline(x=df["avg_delay"].mean(), color=COLORS["warning"], linestyle="--",
           linewidth=2, label=f"Avg: {df['avg_delay'].mean():.2f}min")
ax.legend(fontsize=10)

for bar, val in zip(bars, df["avg_delay"][::-1]):
    ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
            f"{val:.2f}m", va="center", fontsize=9, color="#e0e0e0")

fig.tight_layout()
fig.savefig(f"{OUT}/02_company_delay.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/02_company_delay.png")

# ── 图表 3: 月度延误热力图 ────────────────────────────────
print("Chart 3: Monthly delay heatmap")
df = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y', "Service:Date") AS year,
        strftime('%m', "Service:Date") AS month,
        ROUND(AVG("Stop:Arrival delay"), 3) AS avg_delay
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
""")

years = sorted(df["year"].unique())
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
matrix = np.zeros((len(years), 12))
for _, row in df.iterrows():
    yr_idx = years.index(row["year"])
    mo_idx = int(row["month"]) - 1
    matrix[yr_idx, mo_idx] = row["avg_delay"]

fig, ax = plt.subplots(figsize=(14, 7))
cmap = plt.get_cmap("YlOrRd")
im = ax.imshow(matrix, aspect="auto", cmap=cmap, vmin=0, vmax=2)
ax.set_xticks(range(12))
ax.set_xticklabels(months)
ax.set_yticks(range(len(years)))
ax.set_yticklabels(years)
ax.set_xlabel("Month")
ax.set_ylabel("Year")
ax.set_title("Monthly Average Delay Heatmap (minutes)")

for i in range(len(years)):
    for j in range(12):
        val = matrix[i, j]
        if val > 0:
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=8, color="white" if val > 1.2 else "black")

cbar = fig.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label("Avg Delay (min)", color="#e0e0e0")
cbar.ax.tick_params(color="#a0a0a0")
fig.tight_layout()
fig.savefig(f"{OUT}/03_monthly_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/03_monthly_heatmap.png")

# ── 图表 4: 时段分析 + 工作日对比 ────────────────────────
print("Chart 4: Time-of-day + weekday patterns")

# 时段
df_time = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        CASE
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 0 AND 4 THEN '00-04 Night'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 5 AND 6 THEN '05-06 Early'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 7 AND 9 THEN '07-09 Morning Peak'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 10 AND 12 THEN '10-12 Late Morning'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 13 AND 16 THEN '13-16 Afternoon'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 17 AND 19 THEN '17-19 Evening Peak'
            ELSE '20-24 Night'
        END AS period,
        ROUND(AVG("Stop:Arrival delay"), 3) AS avg_delay
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY avg_delay DESC
""")

# 工作日
df_wday = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        CASE CAST(strftime('%w', "Service:Date") AS INT)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday' END AS day,
        ROUND(AVG("Stop:Arrival delay"), 3) AS avg_delay
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1
""")
day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
df_wday["day"] = df_wday["day"].astype(str)
df_wday = df_wday.set_index("day").reindex(day_order).reset_index()

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# 时段
period_colors = [COLORS["accent"]] * 2 + [COLORS["warning"]] + [COLORS["primary"]] * 4 + [COLORS["accent"]]
axes[0].barh(df_time["period"], df_time["avg_delay"], color=period_colors, edgecolor="none")
axes[0].set_xlabel("Avg Delay (min)")
axes[0].set_title("Delay by Time of Day")
axes[0].invert_yaxis()
for i, (_, row) in enumerate(df_time.iterrows()):
    axes[0].text(row["avg_delay"] + 0.02, i, f"{row['avg_delay']:.2f}m",
                 va="center", fontsize=9, color="#e0e0e0")

# 工作日
wday_colors = [COLORS["primary"]] * 5 + [COLORS["success"]] * 2
axes[1].bar(df_wday["day"], df_wday["avg_delay"], color=wday_colors, edgecolor="none", width=0.7)
axes[1].set_ylabel("Avg Delay (min)")
axes[1].set_title("Delay by Day of Week")
axes[1].set_xticks(range(len(df_wday)))
axes[1].set_xticklabels(df_wday["day"], rotation=30, ha="right")
for i, (_, row) in enumerate(df_wday.iterrows()):
    axes[1].text(i, row["avg_delay"] + 0.02, f"{row['avg_delay']:.2f}m",
                 ha="center", fontsize=9, color="#e0e0e0")
axes[1].axhline(y=df_wday["avg_delay"].mean(), color=COLORS["warning"],
                linestyle="--", linewidth=1.5, label="Mean")
axes[1].legend()

fig.suptitle("Dutch Railway: Time-of-Day & Weekday Delay Patterns", fontsize=14, y=1.02)
fig.tight_layout()
fig.savefig(f"{OUT}/04_time_weekday.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/04_time_weekday.png")

# ── 图表 5: 取消率年度趋势 (填充面积) ────────────────────
print("Chart 5: Cancellation rate trend")
df = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y-%m', "Service:Date") AS month,
        COUNT(*) AS total_stops,
        COUNT(*) FILTER (WHERE "Stop:Arrival cancelled" = TRUE) AS cancelled,
        COUNT(*) FILTER (WHERE "Service:Completely cancelled" = TRUE) AS service_cancelled,
        ROUND(AVG("Stop:Arrival delay"), 3) AS avg_delay
    FROM all_data
    GROUP BY 1 ORDER BY 1
""")

fig, axes = plt.subplots(2, 1, figsize=(15, 10), sharex=True)

# 上图：取消率
ax1 = axes[0]
ax1.fill_between(range(len(df)), df["cancelled"]/df["total_stops"]*100,
                 alpha=0.4, color=COLORS["accent"], label="Stop Cancellations")
ax1.plot(range(len(df)), df["cancelled"]/df["total_stops"]*100,
         color=COLORS["accent"], linewidth=1.5)
ax1.set_ylabel("Stop Cancellation Rate (%)", color=COLORS["accent"])
ax1.tick_params(axis="y", labelcolor=COLORS["accent"])
ax1.grid(alpha=0.3)
ax1.set_title("Monthly Cancellation Rate & Delay Trend (2019-2025)")

# 下图：月度延误 + COVID 阴影
ax2 = axes[1]
ax2.fill_between(range(len(df)), df["avg_delay"], alpha=0.4, color=COLORS["primary"])
ax2.plot(range(len(df)), df["avg_delay"], color=COLORS["primary"], linewidth=1.5, label="Avg Delay")
ax2.set_ylabel("Avg Delay (min)", color=COLORS["primary"])
ax2.tick_params(axis="y", labelcolor=COLORS["primary"])
ax2.grid(alpha=0.3)
ax2.set_xlabel("Month")

# COVID 期间阴影（2020-03 到 2020-05）
covid_months = [(y, m) for y in range(2020, 2021) for m in range(3, 6)]
covid_start = df[df["month"] == "2020-03"].index[0]
covid_end = df[df["month"] == "2020-05"].index[0]
for ax in axes:
    ax.axvspan(covid_start, covid_end, alpha=0.15, color="white", label="COVID Lockdown")
    ax.axvspan(covid_start, covid_end, alpha=0.15, color="white")

# 标签
tick_every = 6
ticks = range(0, len(df), tick_every)
labels = df["month"].iloc[ticks].tolist()
axes[1].set_xticks(list(ticks))
axes[1].set_xticklabels(labels, rotation=45, ha="right")

lines, labs = axes[0].get_legend_handles_labels()
axes[0].legend(lines, labs, loc="upper right")

fig.tight_layout()
fig.savefig(f"{OUT}/05_monthly_cancel_delay.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/05_monthly_cancel_delay.png")

# ── 图表 6: 延误分布直方图 ────────────────────────────────
print("Chart 6: Delay distribution")
# 采样 50 万行做直方图
df = qr(f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT "Stop:Arrival delay"
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL AND "Stop:Arrival delay" >= 0
    USING SAMPLE 500000
""")

fig, ax = plt.subplots(figsize=(12, 6))
bins = [0, 1, 2, 3, 5, 10, 20, 30, 60, 120, 300, 600, 1000, 1500]
ax.hist(df["Stop:Arrival delay"], bins=bins, color=COLORS["primary"],
        edgecolor="none", alpha=0.85, log=True)
ax.set_xscale("log")
ax.set_xlabel("Arrival Delay (minutes, log scale)")
ax.set_ylabel("Count (log scale)")
ax.set_title("Distribution of Arrival Delays (sampled 500K stops)")
ax.axvline(x=5, color=COLORS["accent"], linestyle="--", linewidth=2, label="5min threshold")
ax.axvline(x=15, color=COLORS["orange"], linestyle="--", linewidth=2, label="15min threshold")
ax.legend(fontsize=10)
ax.grid(axis="y", alpha=0.3)

# 统计注释
on_time = (df["Stop:Arrival delay"] == 0).sum()
total = len(df)
ax.text(0.95, 0.95, f"On-time: {on_time/total*100:.1f}%\nTotal: {total:,}",
        transform=ax.transAxes, ha="right", va="top", fontsize=11,
        bbox=dict(boxstyle="round", facecolor="#16213e", alpha=0.8))

fig.tight_layout()
fig.savefig(f"{OUT}/06_delay_distribution.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/06_delay_distribution.png")

con_r.close()

# ═══════════════════════════════════════════════════════════
# SECTION 2: UserBehavior Visualizations
# ═══════════════════════════════════════════════════════════

BASE_UB = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/data/raw"
con_ub = duckdb.connect(":memory:")
con_ub.execute(f"CREATE VIEW ub AS SELECT * FROM read_csv_auto('{BASE_UB}/UserBehavior.csv', header=true)")

def qu(sql):
    return con_ub.execute(sql).fetchdf()

# ── 图表 7: 行为漏斗 + 日转化率 ──────────────────────────
print("Chart 7: Behavior funnel")
df_funnel = qu("""
    SELECT behavior_type, COUNT(*) AS cnt
    FROM ub GROUP BY behavior_type
    ORDER BY cnt DESC
""")
order = ["pv", "fav", "cart", "buy"]
df_funnel = df_funnel.set_index("behavior_type").reindex(order).reset_index()

# 日转化率
df_conv = qu("""
    WITH daily AS (
        SELECT
            date(TO_TIMESTAMP(timestamp)) AS day,
            COUNT(*) FILTER (WHERE behavior_type = 'pv') AS pv,
            COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy
        FROM ub GROUP BY day
    )
    SELECT day, ROUND(buy * 100.0 / pv, 3) AS conv_rate, pv, buy
    FROM daily ORDER BY day
""")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# 漏斗
colors_funnel = [COLORS["primary"], COLORS["secondary"], COLORS["orange"], COLORS["success"]]
bars = axes[0].bar(df_funnel["behavior_type"], df_funnel["cnt"], color=colors_funnel,
                   edgecolor="none", width=0.6)
axes[0].set_xlabel("Behavior Type")
axes[0].set_ylabel("Count")
axes[0].set_title("User Behavior Funnel")
axes[0].set_yscale("log")
for bar, val in zip(bars, df_funnel["cnt"]):
    pct = val / df_funnel["cnt"].iloc[0] * 100
    axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.1,
                 f"{val:,}\n({pct:.1f}%)", ha="center", va="bottom", fontsize=9)

# 转化率趋势
axes[1].fill_between(range(len(df_conv)), df_conv["conv_rate"],
                      alpha=0.4, color=COLORS["success"])
axes[1].plot(range(len(df_conv)), df_conv["conv_rate"],
             color=COLORS["success"], linewidth=2, marker="o", markersize=4)
axes[1].set_xlabel("Day")
axes[1].set_ylabel("Conversion Rate (%)")
axes[1].set_title("Daily Purchase Conversion Rate (pv→buy)")
ticks = range(0, len(df_conv), 2)
axes[1].set_xticks(list(ticks))
axes[1].set_xticklabels([str(d) for d in df_conv["day"].iloc[ticks]], rotation=45, ha="right")
axes[1].axhline(y=df_conv["conv_rate"].mean(), color=COLORS["warning"],
                linestyle="--", linewidth=1.5, label=f"Avg: {df_conv['conv_rate'].mean():.2f}%")
axes[1].legend()
axes[1].grid(alpha=0.3)

fig.suptitle("Taobao UserBehavior: Funnel & Conversion Rate", fontsize=14, y=1.02)
fig.tight_layout()
fig.savefig(f"{OUT}/07_userbehavior_funnel.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/07_userbehavior_funnel.png")

# ── 图表 8: 用户分群 + 行为路径 ──────────────────────────
print("Chart 8: User segments")
df_seg = qu("""
    WITH user_stats AS (
        SELECT user_id,
               COUNT(*) AS total_actions,
               COUNT(DISTINCT behavior_type) AS behavior_diversity,
               COUNT(*) FILTER (WHERE behavior_type = 'buy') AS purchases
        FROM ub GROUP BY user_id
    )
    SELECT
        CASE
            WHEN purchases >= 5 THEN 'VIP (5+ buys)'
            WHEN purchases >= 2 THEN 'Active (2-4 buys)'
            WHEN purchases >= 1 THEN 'Warm (1 buy)'
            ELSE 'Cold (0 buys)'
        END AS segment,
        COUNT(*) AS users,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(DISTINCT user_id) FROM ub), 2) AS pct
    FROM user_stats
    GROUP BY 1
    ORDER BY users DESC
""")

df_path = qu("""
    WITH path_stats AS (
        SELECT user_id,
               MAX(CASE WHEN behavior_type = 'pv' THEN 1 ELSE 0 END) AS has_pv,
               MAX(CASE WHEN behavior_type = 'fav' THEN 1 ELSE 0 END) AS has_fav,
               MAX(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
               MAX(CASE WHEN behavior_type = 'buy' THEN 1 ELSE 0 END) AS has_buy
        FROM ub GROUP BY user_id
    )
    SELECT
        CASE
            WHEN has_buy = 1 AND has_cart = 1 THEN 'pv→cart→buy'
            WHEN has_buy = 1 AND has_cart = 0 AND has_fav = 1 THEN 'pv→fav→buy'
            WHEN has_buy = 1 AND has_cart = 0 AND has_fav = 0 THEN 'pv→buy direct'
            WHEN has_buy = 0 AND has_fav = 1 THEN 'pv→fav (no buy)'
            ELSE 'pv only'
        END AS path,
        COUNT(*) AS users,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM path_stats), 2) AS pct
    FROM path_stats GROUP BY 1 ORDER BY users DESC
""")

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

colors_seg = [COLORS["success"], COLORS["primary"], COLORS["orange"], COLORS["accent"]]
axes[0].pie(df_seg["users"], labels=df_seg["segment"], autopct="%1.1f%%",
            colors=colors_seg, startangle=90, explode=[0.05]*len(df_seg),
            textprops={"color": "#e0e0e0", "fontsize": 10})
axes[0].set_title("User Segments by Purchase Count")

axes[1].barh(df_path["path"], df_path["pct"], color=[COLORS["success"]] * 3 + [COLORS["accent"]] * 2,
             edgecolor="none", height=0.6)
axes[1].set_xlabel("Users (%)")
axes[1].set_title("User Purchase Journey Paths")
for i, (_, row) in enumerate(df_path.iterrows()):
    axes[1].text(row["pct"] + 0.3, i, f"{row['pct']:.1f}% ({row['users']:,})",
                 va="center", fontsize=9, color="#e0e0e0")

fig.suptitle("Taobao UserBehavior: Segments & Purchase Paths", fontsize=14, y=1.02)
fig.tight_layout()
fig.savefig(f"{OUT}/08_userbehavior_segments.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/08_userbehavior_segments.png")

con_ub.close()

# ── 图表 9: 热门时段 + 商品分布 ──────────────────────────
print("Chart 9: Hourly behavior + category distribution")
con_ub2 = duckdb.connect(":memory:")
con_ub2.execute(f"CREATE VIEW ub2 AS SELECT * FROM read_csv_auto('{BASE_UB}/UserBehavior.csv', header=true)")

df_hour = con_ub2.execute("""
    WITH hourly AS (
        SELECT
            TO_TIMESTAMP(timestamp) AS ts,
            behavior_type,
            COUNT(*) AS cnt
        FROM ub2 GROUP BY 1, 2
    )
    SELECT
        EXTRACT(HOUR FROM ts) AS hour,
        behavior_type,
        ROUND(AVG(cnt), 1) AS avg_cnt
    FROM hourly
    GROUP BY 1, 2
    ORDER BY 1
""").fetchdf()

df_cat = con_ub2.execute("""
    SELECT category_id, COUNT(*) AS cnt
    FROM ub2 WHERE behavior_type = 'buy'
    GROUP BY 1 ORDER BY cnt DESC LIMIT 10
""").fetchdf()
con_ub2.close()

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# 小时分布
behaviors = ["pv", "fav", "cart", "buy"]
colors_b = [COLORS["primary"], COLORS["secondary"], COLORS["orange"], COLORS["success"]]
for beh, col in zip(behaviors, colors_b):
    sub = df_hour[df_hour["behavior_type"] == beh]
    axes[0].plot(sub["hour"], sub["avg_cnt"], marker="o", linewidth=2,
                 markersize=5, label=beh.upper(), color=col)
axes[0].set_xlabel("Hour of Day")
axes[0].set_ylabel("Avg Actions per Hour-Slot")
axes[0].set_title("Hourly User Behavior Pattern")
axes[0].set_xticks(range(0, 24, 2))
axes[0].legend()
axes[0].grid(alpha=0.3)
axes[0].axvspan(17, 19, alpha=0.1, color=COLORS["warning"], label="Peak")

# 热门类目
top_cat = df_cat.head(10)
axes[1].barh(top_cat["category_id"].astype(str), top_cat["cnt"],
             color=COLORS["primary"], edgecolor="none")
axes[1].set_xlabel("Purchase Count")
axes[1].set_ylabel("Category ID")
axes[1].set_title("Top 10 Categories by Purchase Volume")
axes[1].invert_yaxis()
for i, (_, row) in enumerate(top_cat.iterrows()):
    axes[1].text(row["cnt"] + 50, i, f"{row['cnt']:,}", va="center", fontsize=9)

fig.suptitle("Taobao: Hourly Behavior & Top Categories", fontsize=14, y=1.02)
fig.tight_layout()
fig.savefig(f"{OUT}/09_userbehavior_hourly.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  -> {OUT}/09_userbehavior_hourly.png")

# ── Summary ──────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"ALL CHARTS SAVED TO: {OUT}")
print("="*60)
