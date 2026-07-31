#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 xianyu_captcha_solve_record 表的近期记录分布"""
import os
import sys
import pymysql
import json

# 读 env
def read_env(path):
    env = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:
        print(f'WARN read env {path}: {e}')
    return env

# 默认连接 automation-service 用的 MySQL
host = os.environ.get('DB_HOST') or os.environ.get('MYSQL_HOST') or 'xianyu-mysql'
port = int(os.environ.get('DB_PORT') or os.environ.get('MYSQL_PORT') or '3306')
user = os.environ.get('DB_USER') or os.environ.get('MYSQL_USER') or 'xianyu'
password = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD') or 'xianyu_pass'
db = os.environ.get('DB_NAME') or os.environ.get('MYSQL_DATABASE') or 'xianyu_assistant_admin'

print(f'Connecting to MySQL {user}@{host}:{port}/{db}')
try:
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db,
                            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
except Exception as e:
    print(f'connect failed: {e}')
    sys.exit(1)

cur = conn.cursor()

print()
print('=== 表结构 ===')
cur.execute("DESCRIBE xianyu_captcha_solve_record")
for r in cur.fetchall():
    print(r)

print()
print('=== 最近 2 小时状态分布 ===')
cur.execute("""
    SELECT status, failure_reason, COUNT(*) AS cnt
    FROM xianyu_captcha_solve_record
    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
    GROUP BY status, failure_reason
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(r)

print()
print('=== 最近 24 小时状态分布 ===')
cur.execute("""
    SELECT status, failure_reason, COUNT(*) AS cnt
    FROM xianyu_captcha_solve_record
    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    GROUP BY status, failure_reason
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(r)

print()
print('=== 最近 20 条记录 ===')
cur.execute("""
    SELECT id, account_id, status, failure_reason, retry_count,
            LEFT(error_message, 300) AS err, created_at
    FROM xianyu_captcha_solve_record
    ORDER BY created_at DESC
    LIMIT 20
""")
for r in cur.fetchall():
    print(r)

conn.close()
