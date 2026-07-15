from pathlib import Path
p = Path(r"apps/automation-service/app/services/ws_client.py")
for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
    c = line.count('"')
    if c % 2 == 1:
        safe = line.encode('ascii', 'backslashreplace').decode('ascii')
        print(i, c, safe)
