import pymysql
import bcrypt

new_hash = bcrypt.hashpw(b'demo123456', bcrypt.gensalt(10)).decode()
print(f'New hash: {new_hash}')

conn = pymysql.connect(host='localhost', user='root', password='123456', database='xianyu_assistant_admin', charset='utf8mb4')
cur = conn.cursor()
cur.execute("UPDATE sys_user SET password_hash=%s WHERE username='demo' AND deleted=0", (new_hash,))
conn.commit()
print('Updated')

# Verify
cur.execute("SELECT password_hash FROM sys_user WHERE username='demo' AND deleted=0")
row = cur.fetchone()
result = bcrypt.checkpw(b'demo123456', row[0].encode())
print(f'Verify: {result}')
conn.close()
