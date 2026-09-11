import os
import sys

# Limita o paralelismo antes de carregar o motor analítico.
cpu_count=os.cpu_count() or 2
os.environ.setdefault("POLARS_MAX_THREADS",str(max(1,min(4,cpu_count//2))))

if sys.platform=="win32":
    try:
        import ctypes
        BELOW_NORMAL_PRIORITY_CLASS=0x00004000
        kernel32=ctypes.windll.kernel32
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(),BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass

from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host=os.getenv('APP_HOST','0.0.0.0'),port=int(os.getenv('PORT','8000')),reload=False)
