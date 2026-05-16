# Useful commands (CollabNote)

Run the API locally (with dependencies and `.env` configured):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Elasticsearch (`vm.max_map_count`)

Set for the current shell session (Linux / VM):

```bash
sudo sysctl -w vm.max_map_count=262144
sysctl vm.max_map_count
```

## Health checks

Elasticsearch cluster health:

```bash
curl "http://localhost:9200/_cluster/health?pretty"
```

MongoDB (adjust container name if yours differs):

```bash
docker exec -it collabnote_mongodb mongosh --eval "db.adminCommand('ping')"
```

Redis:

```bash
docker exec -it collabnote_redis redis-cli ping
```

## Kafka

Create the activity topic (adjust container name to match your Compose stack, e.g. `collabnote_kafka`):

```bash
docker exec -it collabnote_kafka kafka-topics \
  --create \
  --topic activity_logs \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1
```

In a second terminal, with the virtualenv activated:

```bash
source .venv/bin/activate
python -m consumer.consumer
```

Read messages from the beginning of the topic:

```bash
docker exec -it collabnote_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic activity_logs \
  --from-beginning
```

Consumer group status:

```bash
docker exec -it collabnote_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group log_consumer_group
```

## Nginx round-robin (through port 80)

Each new `curl` connection may hit a different upstream instance (`instance_id` in JSON):

```bash
for i in {1..6}; do
  curl -s http://localhost/ | grep -o '"instance_id":"[^"]*"'
done
```

Full JSON response:

```bash
curl http://localhost/
```

chNF
chNF
