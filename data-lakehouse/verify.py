import subprocess, json, time

COMPOSE = [docker, compose, -f, C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/docker-compose.yml]
JM = COMPOSE + [exec, -T, jobmanager, flink]

def curl_cmd(sql):
    body = json.dumps({statement: sql})
    cmd = COMPOSE + [exec, -T, trino, sh, -c, curl -s -X POST http://localhost:8080/v1/statement -H Content-Type: application/json -H X-Trino-User: test --data-binary @-]
    p = subprocess.run(cmd, input=body, capture_output=True, text=True)
    return p.stdout

def poll(uri):
    cmd = COMPOSE + [exec, -T, trino, sh, -c, curl -s + uri + -H X-Trino-User: test]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout

def query_table(table):
    sql = SELECT COUNT(*) FROM iceberg.default. + table
    print(=== Table:  + table +  ===)
    initial = curl_cmd(sql)
    print(INITIAL:  + initial)
    data = json.loads(initial)
    next_uri = data.get(nextUri, )
    for i in range(1, 19):
        time.sleep(5)
        r = poll(next_uri)
        obj = json.loads(r)
        state = obj.get(stats, {}).get(state, UNKNOWN)
        print(Poll  + str(i) +  - state:  + state)
        if state in (FINISHED, FAILED):
            print(RESULT:  + r)
            return
    print()

query_table(user_behavior_dwd)
query_table(user_behavior_pvuv_1m)
query_table(item_hot_1h)

print(=== Flink Job Status Summary ===)
r = subprocess.run(JM + [list], capture_output=True, text=True)
print(r.stdout)
