#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理 xianyu_captcha_solve_record 表中卡死的 retrying 状态记录。

容器重启会导致内存队列丢失，重启前已 retrying 的任务永远不会被 worker 消费，
必须清理为 fail，避免污染统计和阻塞去重。
"""
import os
import sys
import pymysql

host = os.environ.get('DB_HOST') or os.environ.get('MYSQL_HOST') or 'xianyu-mysql'
port = int(os.environ.get('DB_PORT') or os.environ.get('MYSQL_PORT') or '3306')
user = os.environ.get('DB_USER') or os.environ.get('MYSQL_USER') or 'xianyu'
password = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD') or 'xianyu_pass'
db = os.environ.get('DB_NAME') or os.environ.get('MYSQL_DATABASE') or 'xianyu_assistant_admin'

print(f'Connecting to MySQL {user}@{host}:{port}/{db}')
conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db,
                        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
cur = conn.cursor()

print()
print('=== 清理前 retrying 状态记录数 ===')
cur.execute("SELECT COUNT(*) AS cnt FROM xianyu_captcha_solve_record WHERE status='retrying' AND deleted=0")
print(cur.fetchone())

print()
print('=== 清理：将 retrying 改为 fail（failure_reason=service_unavailable） ===')
cur.execute("""
    UPDATE xianyu_captcha_solve_record
    SET status='fail',
        failure_reason='service_unavailable',
        error_message=CONCAT(IFNULL(error_message,''), ' | 容器重启清理：retrying 状态超时未消费'),
        finished_at=NOW(),
        updated_at=NOW()
    WHERE status='retrying' AND deleted=0
""")
print(f'affected rows: {cur.rowcount}')
conn.commit()

print()
print('=== 清理后 retrying 状态记录数 ===')
cur.execute("SELECT COUNT(*) AS cnt FROM xianyu_captcha_solve_record WHERE status='retrying' AND deleted=0")
print(cur.fetchone())

print()
print('=== 当前 queued 状态记录数（应为 0） ===')
cur.execute("SELECT COUNT(*) AS cnt FROM xianyu_captcha_solve_record WHERE status='queued' AND deleted=0")
print(cur.fetchone())

conn.close()
