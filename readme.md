uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Set it for current session

sudo sysctl -w vm.max_map_count=262144

# Verify it's set

sysctl vm.max_map_count

# Check Elasticsearch health:

curl http://localhost:9200/\_cluster/health?pretty
