uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Set it for current session

sudo sysctl -w vm.max_map_count=262144

# Verify it's set

sysctl vm.max_map_count

# Check Elasticsearch health:

curl http://localhost:9200/\_cluster/health?pretty

# Check MongoDB

docker exec -it collabnote_mongodb mongosh --eval "db.adminCommand('ping')"

# Check Redis

docker exec -it collabnote_redis redis-cli ping

# Create the topic for activity logs

docker exec -it lab8_kafka kafka-topics \
 --create \
 --topic activity_logs \
 --bootstrap-server localhost:9092 \
 --partitions 1 \
 --replication-factor 1
