from pathlib import Path
import re

path = Path(r'apps/automation-service/app/services/ws_client.py')
text = path.read_text(encoding='utf-8', errors='replace')
lines = text.splitlines()
pattern = re.compile(r'\s{4,}(?:if |elif |else:|try:|except |await |return |from |async def |self\.|asyncio\.|client =|ws =|now_ts =|last_solve_ts =|_AUTO_SOLVE_LAST_TS|logger\.|result =|row =|reason =|cookie_str =|m_h5_tk =|tenant_id =|unb =|access_token,|headers =|mid =|message =|msg =|fut =|payload =|resp =|request_id =|preserve_|selected =|deletedConversations|contextMessages)')
changed = True
while changed:
    changed = False
    next_lines = []
    for line in lines:
        hash_index = line.find('#')
        if hash_index >= 0:
            match = pattern.search(line, hash_index + 1)
            if match:
                comment = line[:match.start()].rstrip()
                code = line[match.start():]
                if comment:
                    next_lines.append(comment)
                next_lines.append(code)
                changed = True
                continue
        next_lines.append(line)
    lines = next_lines
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('changed', changed, 'lines', len(lines))
