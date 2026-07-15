import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    import subprocess
    import socket as _socket

    # 启动前清理12401端口上的旧进程
    try:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, shell=True
        )
        for line in result.stdout.splitlines():
            if "12401" in line and "LISTENING" in line:
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    try:
                        subprocess.run(["taskkill", "/F", "/PID", pid],
                                     capture_output=True, text=True, shell=True)
                    except Exception:
                        pass
    except Exception:
        pass

    # Patch socket.socket.__init__ to always set SO_REUSEADDR
    # Workaround for Windows zombie TCP port entries
    _orig_init = _socket.socket.__init__

    def _patched_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        try:
            self.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        except OSError:
            pass

    _socket.socket.__init__ = _patched_init

    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=12401,
        reload=False,
        access_log=False,
        log_level="info"
    )

    # Restore original __init__ after uvicorn exits
    _socket.socket.__init__ = _orig_init
