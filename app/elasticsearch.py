import os

from dotenv import load_dotenv

from elasticsearch import AsyncElasticsearch

load_dotenv()

ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "notes")

es_client:AsyncElasticsearch=None


async def connect_to_elasticsearch():
    global es_client
    es_client=AsyncElasticsearch([ELASTICSEARCH_URL])


    info= await es_client.info()
    print(f"Connected to Elasticsearch: {info['version']['number']}")

    if not await es_client.indices.exists(index=ELASTICSEARCH_INDEX):
        await es_client.indices.create(
            index=ELASTICSEARCH_INDEX,
            body={
                "mappings":{
                    "properties":{
                        "title": {"type": "text"},
                        "content": {"type": "text"},
                        "tags": {"type": "keyword"},
                        "created_at": {"type": "date"}
                    }
                }
            }
        )
        print(f"created elastic search index:{ELASTICSEARCH_INDEX}")


async def close_elasticsearch_connection():
    global es_client
    if es_client:
        await es_client.close()
        print("Closed Elasticsearch connection")



def get_elasticsearch():
    return es_client

