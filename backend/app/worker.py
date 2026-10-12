"""Durable upload outbox → Kafka → idempotent ingestion; failures go to a DLQ."""
import asyncio
import json
import logging
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from .config import settings
from .store import init, db
from .ingestion import ingest

logging.basicConfig(level=logging.INFO)
log=logging.getLogger(__name__)

async def dispatch(producer):
    while True:
        with db() as c:
            rows=c.execute('SELECT * FROM outbox WHERE sent=0 LIMIT 20').fetchall()
        for row in rows:
            await producer.send_and_wait('document.uploaded',json.dumps({'document':row['document']}).encode(),key=row['document'].encode())
            with db() as c:
                c.execute('UPDATE outbox SET sent=1 WHERE id=?',(row['id'],))
        await asyncio.sleep(1)

async def consume(consumer,producer):
    async for message in consumer:
        payload=json.loads(message.value)
        for attempt in range(3):
            try:
                await ingest(payload['document'])
                break
            except Exception:
                log.exception('Ingestion failed; attempt %s',attempt+1)
                if attempt==2:
                    await producer.send_and_wait('document.failed',json.dumps(payload).encode())
                else:
                    await asyncio.sleep(2**attempt)
        # Commit only after durable success or acknowledged DLQ publication.
        await consumer.commit()

async def main():
    init()
    while True:
        producer=AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap)
        consumer=AIOKafkaConsumer('document.uploaded',bootstrap_servers=settings.kafka_bootstrap,group_id='ingestion-v1',enable_auto_commit=False,auto_offset_reset='earliest',max_poll_interval_ms=1800000)
        try:
            await producer.start()
            await consumer.start()
            async with asyncio.TaskGroup() as group:
                group.create_task(dispatch(producer))
                group.create_task(consume(consumer,producer))
        except Exception:
            log.exception('Worker disconnected; reconnecting')
        finally:
            await consumer.stop()
            await producer.stop()
        await asyncio.sleep(5)

if __name__=='__main__':
    asyncio.run(main())
