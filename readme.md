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

# In terminal 2 - Run consumer

source .venv/bin/activate

python -m consumer.consumer

# View messages in the topic (from beginning)

docker exec -it lab8_kafka kafka-console-consumer \
 --bootstrap-server localhost:9092 \
 --topic activity_logs \
 --from-beginning

# Check consumer group status

docker exec -it lab8_kafka kafka-consumer-groups \
 --bootstrap-server localhost:9092 \
 --describe \

Step 6: Test Round-Robin Load Balancing
Test 1: Verify rotation with curl

# Make 6 requests and extract instance_id

for i in {1..6}; do
curl -s http://localhost/ | grep -o '"instance_id":"[^"]\*"'
done

Why this works: Each curl command creates a new TCP connection. Nginx's round-robin picks the next server for each new connection.

Test 2: View full response

curl http://localhost
