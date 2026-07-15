import pymysql
import bcrypt

conn = pymysql.connect(host='localhost', user='root', password='123456', database='xianyu_assistant_admin', charset='utf8mb4')
cur = conn.cursor()
cur.execute("SELECT id, username, password_hash FROM sys_user WHERE username='demo' AND deleted=0")
row = cur.fetchone()
print(f'id={row[0]}, username={row[1]}, hash={row[2][:40]}...')
test_pwd = 'demo123456'
try:
    result = bcrypt.checkpw(test_pwd.encode(), row[2].encode())
    print(f'Verify demo123456: {result}')
except Exception as e:
    print(f'Verify error: {e}')
conn.close()
