#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kafka Replay Producer v2 (fixed: speedup logic + kafka-python 3.x compat + log file)."""
import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from kafka import KafkaProducer

LOG_PATH = os.path.join(os.path.dirname(__file__), "producer.log")


def open_log():
    f = open(LOG_PATH, "w", encoding="utf-8")
    return f


def log(f, msg):
    f.write(msg + "\n")
    f.flush()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--kafka", default="localhost:9092")
    p.add_argument("--topic", default="user-behavior")
    p.add_argument("--speedup", type=float, default=0.0,
                   help="speedup vs realtime; 0 = max speed (no pacing)")
    p.add_argument("--batch-size", type=int, default=10000)
    args = p.parse_args()

    logf = open_log()
    try:
        log(logf, f"input={args.input} kafka={args.kafka} topic={args.topic} speedup={args.speedup}")

        producer = KafkaProducer(
            bootstrap_servers=args.kafka,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: str(k).encode("utf-8") if k else None,
            acks=1,
            linger_ms=20,
            batch_size=32768,
        )

        with open(args.input, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        total = len(rows)
        log(logf, f"rows={total}")
        if total == 0:
            log(logf, "empty csv")
            return

        t0 = time.time()
        sent = 0
        first_ts = int(rows[0]["timestamp"])
        first_real = datetime.fromtimestamp(first_ts)
        last_ts = int(rows[-1]["timestamp"])
        log(logf, f"data range: {first_real} -> {datetime.fromtimestamp(last_ts)} ({total} rows)")

        log(logf, "sending...")
        for row in rows:
            ts = int(row["timestamp"])
            event = {
                "user_id": int(row["user_id"]),
                "item_id": int(row["item_id"]),
                "category_id": int(row["category_id"]),
                "behavior_type": row["behavior_type"],
                "ts": ts,
                "event_time": datetime.fromtimestamp(ts).isoformat(),
            }
            producer.send(args.topic, key=row["user_id"], value=event)
            sent += 1
            if sent % args.batch_size == 0:
                producer.flush()
                if sent % 100000 == 0 or sent == total:
                    elapsed = time.time() - t0
                    rate = sent / max(elapsed, 1e-6)
                    log(logf, f"sent {sent}/{total} ({sent*100/total:.1f}%) {rate:,.0f} msg/s")

            if args.speedup > 0 and sent < total:
                # virtual time pacing: original time between first and current row
                next_ts = int(rows[min(sent, total - 1)]["timestamp"])
                delta_virtual = (next_ts - first_ts) / args.speedup
                elapsed_real = time.time() - t0
                if delta_virtual > elapsed_real:
                    time.sleep(min(delta_virtual - elapsed_real, 1.0))

        producer.flush()
        elapsed = time.time() - t0
        log(logf, f"done sent={sent} elapsed={elapsed:.2f}s rate={sent/max(elapsed,1e-6):,.0f} msg/s")
    finally:
        logf.close()


if __name__ == "__main__":
    main()
