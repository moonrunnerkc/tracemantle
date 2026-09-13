import hashlib
import json
import platform
import statistics
import sys
import time
import tracemalloc
from tracemantle.markdown import tokenize
body = '\n'.join(f'`[example](missing-{i}.md)`\n\n    include: absent-{i}.md\n\n[real](docs/real-{i}.md) and `scripts/helper-{i}.py`\n' for i in range(1000))
results = []
for _ in range(5):
 start=time.perf_counter(); result=tokenize(body); results.append(time.perf_counter()-start)
tracemalloc.start(); result=tokenize(body); peak=tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
print(json.dumps({'python':sys.version,'platform':platform.platform(),'corpus_sha256':hashlib.sha256(body.encode()).hexdigest(),'corpus_bytes':len(body.encode()),'repeats':5,'seconds':results,'median':statistics.median(results),'spread':max(results)-min(results),'peak_python_bytes':peak,'resource_count':len(result.resources),'uncertain':result.uncertain},indent=2))
