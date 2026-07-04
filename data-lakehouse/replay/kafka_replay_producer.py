#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import csv
import json
import time
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

class KafkaReplayProducer:
    def __init__(self, bootstrap_servers, topic, speedup, batch_size):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.speedup = speedup
        self.batch_size = batch_size
        self.producer = None
        self.sent = 0
        self.start_time = None
        self.first_timestamp = None
        self.last_timestamp = None
        
    def _create_producer(self):
        return KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            key_serializer=lambda k: str(k).encode('utf-8') if k else None,
            acks='all',
            retries=3,
            max_in_flight_requests_per_connection=1,
            linger_ms=50,
            batch_size=16384 * 4,
        )
        
    def run(self):
        print('Reading CSV: data-lakehouse/data/raw/UserBehavior.csv')
        print(f'Kafka: {self.bootstrap_servers}, Topic: {self.topic}')
        print(f'Speedup: {self.speedup}x')
        
        self.producer = self._create_producer()
        
        with open('data-lakehouse/data/raw/UserBehavior.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            rows = list(reader)
            total_rows = len(rows)
            print(f'Scanning dataset...')
            print(f'Data range: {rows[0]["timestamp"]} -> {rows[-1]["timestamp"]} ({total_rows:,} total records)')
            print(f'Original time range: {datetime.fromtimestamp(int(rows[0]["timestamp"]))} -> {datetime.fromtimestamp(int(rows[-1]["timestamp"]))}')
            print()
            print('Starting to send messages...')
            
            self.start_time = time.time()
            self.first_timestamp = int(rows[0]['timestamp'])
            
            for i, row in enumerate(rows):
                user_id = row['user_id']
                item_id = row['item_id']
                category_id = row['category_id']
                behavior = row['behavior_type']
                timestamp = int(row['timestamp'])
                
                event = {
                    'user_id': int(user_id),
                    'item_id': int(item_id),
                    'category_id': int(category_id),
                    'behavior_type': behavior,
                    'ts': timestamp,
                    'event_time': datetime.fromtimestamp(timestamp).isoformat()
                }
                
                self.producer.send(self.topic, key=user_id, value=event)
                self.sent += 1
                
                if self.sent % 100000 == 0:
                    elapsed = time.time() - self.start_time
                    rate = self.sent / elapsed
                    print(f'Sent {self.sent:,} / {total_rows:,} ({self.sent*100/total_rows:.1f}%) - {rate:,.0f} msg/s')
                
                if self.sent % self.batch_size == 0:
                    self.producer.flush()
                    
            self.producer.flush()
            
            elapsed = time.time() - self.start_time
            print()
            print('Complete!')
            print(f'Total sent: {self.sent:,} messages')
            print(f'Time elapsed: {elapsed:.2f} seconds')
            print(f'Average rate: {self.sent/elapsed:,.0f} messages/second')

def main():
    parser = argparse.ArgumentParser(description='Kafka Replay Producer')
    parser.add_argument('--input', default='data-lakehouse/data/raw/UserBehavior.csv', help='Input CSV file')
    parser.add_argument('--kafka', default='localhost:9092', help='Kafka bootstrap servers')
    parser.add_argument('--topic', default='user-behavior', help='Kafka topic')
    parser.add_argument('--speedup', type=float, default=1, help='Speedup factor (0 = max speed)')
    parser.add_argument('--batch-size', type=int, default=10000, help='Flush batch size')
    
    args = parser.parse_args()
    
    producer = KafkaReplayProducer(
        bootstrap_servers=args.kafka,
        topic=args.topic,
        speedup=args.speedup,
        batch_size=args.batch_size
    )
    producer.run()

if __name__ == '__main__':
    main()

