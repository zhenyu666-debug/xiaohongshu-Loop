# 数据集说明文档

## 数据集来源

**淘宝用户购物行为数据集（UserBehavior）**

- 官方地址：https://tianchi.aliyun.com/dataset/649
- 原始文件：`UserBehavior.csv.zip`（约 906MB 压缩 / 3.4GB 解压）
- 记录数量：约 1 亿条（100,150,807 条）
- 时间范围：2017-11-25 至 2017-12-03（共 9 天）

## 数据格式

CSV 格式，每行一条用户行为，以逗号分隔，无表头：

```
user_id,item_id,category_id,behavior_type,timestamp
123456,100000,5000,pv,1511577600
```

### 字段说明

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| user_id | BIGINT | 序列化后的用户 ID | 123456 |
| item_id | BIGINT | 序列化后的商品 ID | 100000 |
| category_id | BIGINT | 序列化后的商品类目 ID | 5000 |
| behavior_type | STRING | 行为类型枚举 | pv/buy/cart/fav |
| timestamp | BIGINT | Unix 时间戳（秒级，**注意：北京时间 UTC+8**） | 1511577600 |

### 行为类型

| 类型 | 说明 |
|------|------|
| `pv` | Page View，商品详情页点击 |
| `buy` | 商品购买 |
| `cart` | 将商品加入购物车 |
| `fav` | 收藏商品 |

## 时间戳注意事项

**重要**：该数据集的时间戳是北京时间（UTC+8），在数据处理时需要注意：

```python
# 错误示例：直接转换会差 8 小时
from datetime import datetime
dt = datetime.utcfromtimestamp(1511577600)
# 结果: 2017-11-24 16:00:00 (前一天!)

# 正确做法：加上 8 小时或使用本地时区
from datetime import datetime, timezone, timedelta
tz_cst = timezone(timedelta(hours=8))
dt = datetime.fromtimestamp(1511577600, tz=tz_cst)
# 结果: 2017-11-25 00:00:00
```

## 数据预处理

原始 CSV 文件有以下问题需要处理：

1. **乱序**：数据并非按时间字段排序，Flink Watermark 需要容忍乱序
2. **可能含无效行**：需过滤 user_id/item_id/category_id <= 0 的记录
3. **加速回放**：
   - 原始时间跨度 9 天，1:1 回放太慢
   - 推荐 `--speedup 3600`（1 秒播放 1 小时，9 天约 3.75 小时播完）
   - 如果想要更快，可使用 `--speedup 86400`（1 秒播放 1 天，约 9 秒播完）

## 获取数据集

### 方式一：天池官网下载（推荐）

1. 访问 https://tianchi.aliyun.com/dataset/649
2. 登录阿里云账号
3. 点击「下载」获取 `UserBehavior.csv.zip`
4. 解压后重命名为 `UserBehavior.csv`
5. 放入 `data-lakehouse/data/raw/` 目录

### 方式二：GitHub 镜像

已有社区预处理好的去重+排序版本：

```
# 7z 压缩版（约 400MB）
https://github.com/zq2599/blog_download_files/tree/master/files
```

### 方式三：脚本下载

运行 `replay/download_dataset.py`（需提供天池 Cookie）：

```bash
python replay/download_dataset.py \
    --cookie "your-tianchi-cookie" \
    --output data/raw/UserBehavior.csv
```

## 数据规模参考

| 指标 | 数值 |
|------|------|
| 总记录数 | ~100,150,807 |
| 文件大小 | 3.4 GB（未压缩）|
| 用户数 | ~987,994（≈100 万）|
| 商品数 | ~4,083,819（≈400 万）|
| 类目数 | ~9,439（≈1 万）|
| 每天平均记录 | ~11,127,867（≈1100 万）|

## 行为分布参考（来自社区统计）

| 行为类型 | 占比 |
|------|------|
| pv（点击）| ~88.4% |
| fav（收藏）| ~4.6% |
| cart（加购）| ~4.4% |
| buy（购买）| ~2.6% |

## 数据质量说明

- `user_id = 0` 或 `item_id = 0` 的记录需过滤
- 部分 `category_id` 可能为 0
- 数据集为脱敏数据，`user_id` 和 `item_id` 已做哈希处理
- 部分类目 ID 不在类目表中，无法做维表关联
