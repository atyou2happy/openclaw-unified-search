#!/bin/bash
# Start unified-search service
cd /mnt/g/knowledge/project/unified-search
conda run -n stock python -m uvicorn app.main:app --host 127.0.0.1 --port 8900 --log-level info
