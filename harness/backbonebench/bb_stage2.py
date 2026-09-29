"""백본 비교 ② 기동·기능 측정 클라이언트 (EXP-BB, 측정 도구 — 솔루션 부품 아님).

    python /repo/harness/backbonebench/bb_stage2.py run --profile kafka43 --adapter kafka --variant base \
        --devices 1 --hz 1 --duration 120
    python /repo/harness/backbonebench/bb_stage2.py telegraf --profile kafka43        # Telegraf 1.40 입출력 호환(#17570)
    python /repo/harness/backbonebench/bb_stage2.py summarize --profile kafka43       # → experiments/EXP-BB/stage2_<profile>.json

run 한 번이 재는 것 (harness/SCHEMA.md §3 raw 레코드 모양, V1 토픽 = sensor.telemetry.raw 6파티션·24h·키=tag):
  1. 발행: 12태그 × N장치 × hz, 레코드마다 seq·emit_ns·run 추가(SCHEMA §4)
  2. 실시간 소비(같은 컨테이너 → 같은 시계): 지연 = 수신 ns - emit_ns → p50/p95/p99/max
  3. 판정: (장치,태그)별 seq 로 유실·중복·키 안 순서 뒤바뀜 (ROBUSTNESS 정답: 기대 = 12 × 초 × N)
  4. 재생(E6·F11, V1 은 Kafka 오프셋 재생에 의존): 발행 중간 시각 이후를
     (a) 위치(오프셋/시퀀스) 기준, (b) 시각 기준으로 새 소비자가 다시 읽어 원본 부분집합과 대조
  5. --restart-note: 호스트가 run 도중 브로커를 재시작한 경우(R03) 표시만 남긴다(재시작은 stage2.sh 가 한다)
결과: /experiments/EXP-BB/raw/<profile>_<variant>.json
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import glob
import json
import os
import pathlib
import sys
import threading
import time
import uuid

sys.path.insert(0, "/repo/harness/benchcommon")
import telemetry as T  # noqa: E402

RAW = pathlib.Path("/experiments/EXP-BB/raw")
TOPIC = "sensor.telemetry.raw"          # V1 이름(SCHEMA §3)
PARTITIONS = 6
RETENTION_MS = 86_400_000


# ─────────────────────────────── 어댑터 ───────────────────────────────
class Adapter:
    """모든 어댑터 공통: 위치(pos)는 JSON 직렬화 가능한 값. replay_* 는 (payload bytes) 목록을 돌려준다."""
    name = "?"
    topic_name = TOPIC
    supports = {"replay_position": True, "replay_time": True, "partitions": PARTITIONS}

    async def setup(self): ...
    async def start_consumer(self, on_msg): ...
    async def send(self, key: str, payload: bytes): ...
    async def flush(self): ...
    async def replay_position(self, positions: dict, stop_when, timeout: float) -> list[bytes]: return []
    async def replay_time(self, t_ms: int, stop_when, timeout: float) -> list[bytes]: return []
    async def close(self): ...


class KafkaAdapter(Adapter):
    """Kafka 프로토콜(Apache Kafka·AutoMQ·Tansu). V1 Telegraf#1 과 같은 acks=all·lz4·키=tag."""
    name = "kafka"

    def __init__(self, a):
        from confluent_kafka import Producer
        self.bs = a.bootstrap or "kafka:9092"
        self.run = a.run_id
        self.p = Producer({"bootstrap.servers": self.bs, "acks": "all", "compression.type": "lz4",
                           "linger.ms": 5, "message.timeout.ms": 60000})
        self.errors = 0
        self.stop = threading.Event()

    async def setup(self):
        from confluent_kafka.admin import AdminClient, NewTopic
        ad = AdminClient({"bootstrap.servers": self.bs})
        if TOPIC not in ad.list_topics(timeout=30).topics:
            f = ad.create_topics([NewTopic(TOPIC, PARTITIONS, 1, config={
                "retention.ms": str(RETENTION_MS), "compression.type": "lz4"})])
            for fut in f.values():
                try:
                    fut.result(30)
                except Exception as e:  # 이미 있음 등
                    if "TOPIC_ALREADY_EXISTS" not in str(e):
                        raise

    def _consume(self, group, on_msg, assign=None, stop=None):
        from confluent_kafka import Consumer
        c = Consumer({"bootstrap.servers": self.bs, "group.id": group, "auto.offset.reset": "earliest",
                      "enable.auto.commit": False})
        if assign:
            c.assign(assign)
        else:
            c.subscribe([TOPIC])
        stop = stop or self.stop
        while not stop.is_set():
            m = c.poll(0.2)
            if m is None or m.error():
                continue
            on_msg(m.value(), {"p": m.partition(), "o": m.offset(), "ts_ms": m.timestamp()[1]})
        c.close()

    async def start_consumer(self, on_msg):
        threading.Thread(target=self._consume, args=(f"bb-live-{self.run}", on_msg), daemon=True).start()

    async def send(self, key, payload):
        def cb(err, msg):
            if err:
                self.errors += 1
        while True:
            try:
                self.p.produce(TOPIC, payload, key=key.encode(), on_delivery=cb)
                break
            except BufferError:
                self.p.poll(0.05)
        self.p.poll(0)

    async def flush(self):
        await asyncio.to_thread(self.p.flush, 60)

    async def _collect(self, assign, stop_when, timeout):
        got, stop = [], threading.Event()
        th = threading.Thread(target=self._consume, args=(f"bb-replay-{uuid.uuid4().hex[:8]}",
                              lambda v, pos: got.append(v), assign, stop), daemon=True)
        th.start()
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        stop.set()
        th.join(5)
        return got

    async def replay_position(self, positions, stop_when, timeout):
        from confluent_kafka import TopicPartition
        return await self._collect([TopicPartition(TOPIC, int(p), int(o)) for p, o in positions.items()],
                                   stop_when, timeout)

    async def replay_time(self, t_ms, stop_when, timeout):
        from confluent_kafka import Consumer, TopicPartition
        c = Consumer({"bootstrap.servers": self.bs, "group.id": "bb-ofs"})
        tps = c.offsets_for_times([TopicPartition(TOPIC, p, t_ms) for p in range(PARTITIONS)], timeout=30)
        c.close()
        return await self._collect([TopicPartition(TOPIC, tp.partition, tp.offset) for tp in tps if tp.offset >= 0],
                                   stop_when, timeout)

    async def close(self):
        self.stop.set()


class NatsAdapter(Adapter):
    """NATS JetStream. 스트림 1개(주제 sensor.telemetry.raw.<device>.<tag>) — 파티션 없음, 스트림 전체가 한 순서."""
    name = "nats"
    supports = {"replay_position": True, "replay_time": True, "partitions": 1}

    def __init__(self, a):
        self.url = a.bootstrap or "nats://nats:4222"
        self.run = a.run_id
        self.errors = 0
        self.pending = []

    async def setup(self):
        import nats
        from nats.js.api import StreamConfig, StorageType
        self.nc = await nats.connect(self.url, max_reconnect_attempts=-1, reconnect_time_wait=1)
        self.js = self.nc.jetstream()
        try:
            await self.js.add_stream(StreamConfig(name="SENSOR_TELEMETRY_RAW", subjects=[TOPIC + ".>"],
                                                  max_age=RETENTION_MS / 1000, storage=StorageType.FILE,
                                                  num_replicas=1))
        except Exception as e:
            if "already in use" not in str(e):
                raise

    def _subj(self, key):
        dev, _, tag = key.rpartition("/")
        return f"{TOPIC}.{dev or T.DEVICE0}.{tag}"

    async def _sub(self, cb, cfg):
        return await self.js.subscribe(TOPIC + ".>", cb=cb, ordered_consumer=True, config=cfg)

    async def start_consumer(self, on_msg):
        from nats.js.api import ConsumerConfig, DeliverPolicy

        async def cb(m):
            md = m.metadata
            on_msg(m.data, {"seq": md.sequence.stream, "ts_ms": int(md.timestamp.timestamp() * 1000)})
        self.live = await self._sub(cb, ConsumerConfig(deliver_policy=DeliverPolicy.ALL))

    async def send(self, key, payload):
        async def pub():
            try:
                await self.js.publish(self._subj(key), payload, timeout=30)
            except Exception:
                self.errors += 1
        self.pending.append(asyncio.create_task(pub()))

    async def flush(self):
        await asyncio.gather(*self.pending)
        self.pending = []

    async def _collect(self, cfg, stop_when, timeout):
        got = []

        async def cb(m):
            got.append(m.data)
        sub = await self._sub(cb, cfg)
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        await sub.unsubscribe()
        return got

    async def replay_position(self, positions, stop_when, timeout):
        from nats.js.api import ConsumerConfig, DeliverPolicy
        return await self._collect(ConsumerConfig(deliver_policy=DeliverPolicy.BY_START_SEQUENCE,
                                                  opt_start_seq=int(min(positions.values()))), stop_when, timeout)

    async def replay_time(self, t_ms, stop_when, timeout):
        from datetime import datetime, timezone
        from nats.js.api import ConsumerConfig, DeliverPolicy
        start = datetime.fromtimestamp(t_ms / 1000, timezone.utc)
        return await self._collect(ConsumerConfig(deliver_policy=DeliverPolicy.BY_START_TIME, opt_start_time=start),
                                   stop_when, timeout)

    async def close(self):
        await self.nc.drain()


class PulsarAdapter(Adapter):
    """Pulsar 4.0 LTS standalone. 분할 토픽 6, 네임스페이스 보존 24h(보존 없으면 확인된 메시지는 재생 불가), 키=tag."""
    name = "pulsar"

    def __init__(self, a):
        import pulsar
        self.pulsar = pulsar
        self.svc = a.bootstrap or "pulsar://pulsar:6650"
        self.admin = a.admin or "http://pulsar:8080"
        self.topic = f"persistent://public/default/{TOPIC}"
        self.run = a.run_id
        self.errors = 0
        self.stop = threading.Event()

    async def setup(self):
        import requests
        requests.post(f"{self.admin}/admin/v2/namespaces/public/default/retention",
                      json={"retentionTimeInMinutes": RETENTION_MS // 60000, "retentionSizeInMB": -1}, timeout=30).raise_for_status()
        r = requests.put(f"{self.admin}/admin/v2/persistent/public/default/{TOPIC}/partitions",
                         data=str(PARTITIONS), headers={"Content-Type": "application/json"}, timeout=30)
        if r.status_code not in (204, 409):
            r.raise_for_status()
        self.client = self.pulsar.Client(self.svc, operation_timeout_seconds=30)
        self.p = self.client.create_producer(self.topic, compression_type=self.pulsar.CompressionType.LZ4,
                                             batching_enabled=True, batching_max_publish_delay_ms=5,
                                             block_if_queue_full=True, send_timeout_millis=60000)

    def _loop(self, consumer, on_msg, stop):
        while not stop.is_set():
            try:
                m = consumer.receive(timeout_millis=200)
            except Exception:
                continue
            mid = m.message_id()
            on_msg(m.data(), {"p": mid.partition(), "mid": mid.serialize().hex(), "ts_ms": m.publish_timestamp()})
            consumer.acknowledge(m)
        consumer.close()

    async def start_consumer(self, on_msg):
        c = self.client.subscribe(self.topic, f"bb-live-{self.run}", consumer_type=self.pulsar.ConsumerType.Exclusive,
                                  initial_position=self.pulsar.InitialPosition.Earliest)
        threading.Thread(target=self._loop, args=(c, on_msg, self.stop), daemon=True).start()

    async def send(self, key, payload):
        def cb(res, mid):
            if res != self.pulsar.Result.Ok:
                self.errors += 1
        self.p.send_async(payload, cb, partition_key=key)

    async def flush(self):
        await asyncio.to_thread(self.p.flush)

    async def replay_position(self, positions, stop_when, timeout):
        got, stop, readers = [], threading.Event(), []
        for p, hexid in positions.items():
            r = self.client.create_reader(f"{self.topic}-partition-{p}",
                                          self.pulsar.MessageId.deserialize(bytes.fromhex(hexid)),
                                          start_message_id_inclusive=True)
            readers.append(r)

        def rd(r):
            while not stop.is_set():
                try:
                    got.append(r.read_next(200).data())
                except Exception:
                    continue
        ths = [threading.Thread(target=rd, args=(r,), daemon=True) for r in readers]
        [t.start() for t in ths]
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        stop.set()
        [t.join(5) for t in ths]
        [r.close() for r in readers]
        return got

    async def replay_time(self, t_ms, stop_when, timeout):
        got, stop = [], threading.Event()
        c = self.client.subscribe(self.topic, f"bb-rt-{uuid.uuid4().hex[:8]}",
                                  initial_position=self.pulsar.InitialPosition.Earliest)
        c.seek(t_ms)
        th = threading.Thread(target=self._loop, args=(c, lambda v, pos: got.append(v), stop), daemon=True)
        th.start()
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        stop.set()
        th.join(5)
        return got

    async def close(self):
        self.stop.set()
        time.sleep(0.5)
        self.client.close()


class RabbitStreamAdapter(Adapter):
    """RabbitMQ 4.3 Streams(rstream). 단일 스트림(파티션 없음 — 슈퍼 스트림은 ④에서), max-age 24h."""
    name = "rabbitmq-stream"
    supports = {"replay_position": True, "replay_time": True, "partitions": 1}

    def __init__(self, a):
        self.host = a.bootstrap or "rabbitmq"
        self.user, self.pw = os.environ.get("RMQ_USER", "bench"), os.environ.get("RMQ_PASS", "bench")
        self.errors = 0

    async def setup(self):
        from rstream import Producer
        self.p = Producer(self.host, username=self.user, password=self.pw)
        await self.p.start()
        await self.p.create_stream(TOPIC, arguments={"max-age": "24h"}, exists_ok=True)
        self.batch = []

    async def _consumer(self, spec, cb):
        from rstream import Consumer
        c = Consumer(self.host, username=self.user, password=self.pw)
        await c.start()
        await c.subscribe(TOPIC, cb, offset_specification=spec)
        return c

    async def start_consumer(self, on_msg):
        from rstream import ConsumerOffsetSpecification, OffsetType

        async def cb(msg, ctx):
            on_msg(bytes(msg), {"o": ctx.offset, "ts_ms": ctx.timestamp})
        self.live = await self._consumer(ConsumerOffsetSpecification(OffsetType.FIRST, None), cb)

    async def send(self, key, payload):
        self.batch.append(payload)       # 한 틱(1/hz 초) 분량을 flush_tick 에서 한 번에 보낸다

    async def flush_tick(self):
        if self.batch:
            def conf(status):
                if not status.is_confirmed:
                    self.errors += 1
            await self.p.send_batch(TOPIC, self.batch, on_publish_confirm=conf)
            self.batch = []

    async def flush(self):
        await self.flush_tick()
        await asyncio.sleep(2)

    async def _collect(self, spec, stop_when, timeout):
        got = []

        async def cb(msg, ctx):
            got.append(bytes(msg))
        c = await self._consumer(spec, cb)
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        await c.close()
        return got

    async def replay_position(self, positions, stop_when, timeout):
        from rstream import ConsumerOffsetSpecification, OffsetType
        return await self._collect(ConsumerOffsetSpecification(OffsetType.OFFSET, int(min(positions.values()))),
                                   stop_when, timeout)

    async def replay_time(self, t_ms, stop_when, timeout):
        from rstream import ConsumerOffsetSpecification, OffsetType
        return await self._collect(ConsumerOffsetSpecification(OffsetType.TIMESTAMP, t_ms), stop_when, timeout)

    async def close(self):
        await self.live.close()
        await self.p.close()


class IggyAdapter(Adapter):
    """Apache Iggy 0.9 (TCP). 스트림 sensor / 토픽 telemetry_raw 6파티션(이름에 점 대신 _ — 이름 규칙 [미확인] 회피), 키=tag."""
    name = "iggy"
    topic_name = "sensor/telemetry_raw"

    def __init__(self, a):
        self.addr = a.bootstrap or "iggy:8090"
        self.run = a.run_id
        self.errors = 0
        self.stream, self.topic = "sensor", "telemetry_raw"
        self.stop = False

    async def setup(self):
        from apache_iggy import IggyClient, IggyExpiry
        from datetime import timedelta
        self.c = IggyClient(self.addr)
        await self.c.connect()
        await self.c.login_user(os.environ.get("IGGY_USER", "iggy"), os.environ.get("IGGY_PASS", "iggy-bench-pw"))
        try:
            await self.c.create_stream(self.stream)
        except Exception:
            pass
        try:
            await self.c.create_topic(self.stream, self.topic, PARTITIONS,
                                      message_expiry=IggyExpiry.ExpireDuration(timedelta(hours=24)))
        except Exception:
            pass
        # 파티션 번호 체계(0 시작/1 시작)를 실제로 확인한다
        from apache_iggy import Consumer, PollingStrategy
        self.pids = []
        for pid in range(0, PARTITIONS + 1):
            try:
                await self.c.poll_messages(self.stream, self.topic, consumer=Consumer.Single("probe"),
                                           polling_strategy=PollingStrategy.First(), count=1, auto_commit=False,
                                           partition_id=pid)
                self.pids.append(pid)
            except Exception:
                pass

    async def _poll(self, strategy_for, on_msg, stop_flag, cid):
        from apache_iggy import Consumer, PollingStrategy
        cons = Consumer.Single(cid)
        first = {p: True for p in self.pids}
        while not stop_flag():
            n = 0
            for pid in self.pids:
                strat = strategy_for(pid) if first[pid] else PollingStrategy.Next()
                try:
                    msgs = await self.c.poll_messages(self.stream, self.topic, consumer=cons, polling_strategy=strat,
                                                      count=1000, auto_commit=True, partition_id=pid)
                except Exception:
                    msgs = []
                first[pid] = False
                for m in msgs:
                    on_msg(m.payload(), {"p": pid, "o": m.offset(), "ts_ms": m.timestamp() // 1000})
                n += len(msgs)
            if n == 0:
                await asyncio.sleep(0.01)

    async def start_consumer(self, on_msg):
        from apache_iggy import PollingStrategy
        self.task = asyncio.create_task(self._poll(lambda p: PollingStrategy.First(), on_msg, lambda: self.stop,
                                                   f"bb-live-{self.run}"))

    async def send(self, key, payload):
        from apache_iggy import Partitioning, SendMessage
        try:
            await self.c.send_messages(self.stream, self.topic, Partitioning.messages_key(key), [SendMessage(payload)])
        except Exception:
            self.errors += 1

    async def _collect(self, strategy_for, stop_when, timeout):
        got, t0 = [], time.time()
        await self._poll(strategy_for, lambda v, pos: got.append(v),
                         lambda: stop_when(got) or time.time() - t0 > timeout, f"bb-replay-{uuid.uuid4().hex[:8]}")
        return got

    async def replay_position(self, positions, stop_when, timeout):
        from apache_iggy import PollingStrategy
        return await self._collect(lambda p: PollingStrategy.Offset(int(positions.get(str(p), positions.get(p, 0)))),
                                   stop_when, timeout)

    async def replay_time(self, t_ms, stop_when, timeout):
        from apache_iggy import PollingStrategy
        return await self._collect(lambda p: PollingStrategy.Timestamp(t_ms * 1000), stop_when, timeout)

    async def close(self):
        self.stop = True
        await asyncio.sleep(0.5)


class RocketMQAdapter(Adapter):
    """RocketMQ 5.5 (gRPC proxy 8081). FIFO 토픽 sensor_telemetry_raw(점 금지 규칙), message_group=키(tag).
    오프셋은 클라이언트에 노출되지 않음 → 위치 재생 불가 기록. 시각 재생은 호스트가 mqadmin resetOffsetByTime 실행
    (파일 핸드셰이크: <run>.replay_request → stage2.sh → <run>.replay_done)."""
    name = "rocketmq"
    topic_name = "sensor_telemetry_raw"
    supports = {"replay_position": False, "replay_time": True, "partitions": PARTITIONS}

    def __init__(self, a):
        from rocketmq import ClientConfiguration, Credentials
        self.cfg = ClientConfiguration(a.bootstrap or "rocketmq-broker:8081", Credentials())
        self.run, self.variant, self.profile = a.run_id, a.variant, a.profile
        self.errors = 0
        self.stop = threading.Event()
        self.group = f"bb-live-{a.variant}"          # 그룹은 stage2.sh 가 순서 소비(-o true)로 미리 만든다
        self.rgroup = f"bb-replay-{a.variant}"

    async def setup(self):
        from rocketmq import Producer
        self.p = Producer(self.cfg, (self.topic_name,))
        self.p.startup()

    def _loop(self, group, on_msg, stop):
        from rocketmq import FilterExpression, SimpleConsumer
        c = SimpleConsumer(self.cfg, group, {self.topic_name: FilterExpression()}, await_duration=2)
        c.startup()
        while not stop.is_set():
            try:
                ms = c.receive(32, 15)
            except Exception:
                continue
            for m in ms or []:
                on_msg(m.body, {"ts_ms": m.store_timestamp})
                try:
                    c.ack(m)
                except Exception:
                    pass
        c.shutdown()

    async def start_consumer(self, on_msg):
        threading.Thread(target=self._loop, args=(self.group, on_msg, self.stop), daemon=True).start()

    async def send(self, key, payload):
        from rocketmq import Message
        m = Message()
        m.topic, m.body, m.message_group, m.keys = self.topic_name, payload, key, key
        try:
            await asyncio.to_thread(self.p.send, m)
        except Exception:
            self.errors += 1

    async def flush(self): ...

    async def replay_time(self, t_ms, stop_when, timeout):
        req = RAW / f"{self.profile}_{self.variant}.replay_request"
        done = RAW / f"{self.profile}_{self.variant}.replay_done"
        req.write_text(json.dumps({"group": self.rgroup, "topic": self.topic_name, "t_ms": t_ms}))
        t0 = time.time()
        while not done.exists() and time.time() - t0 < 120:
            await asyncio.sleep(0.5)
        if not done.exists():
            return []
        got, stop = [], threading.Event()
        th = threading.Thread(target=self._loop, args=(self.rgroup, lambda v, pos: got.append(v), stop), daemon=True)
        th.start()
        t0 = time.time()
        while time.time() - t0 < timeout and not stop_when(got):
            await asyncio.sleep(0.2)
        stop.set()
        th.join(20)
        return got

    async def close(self):
        self.stop.set()
        self.p.shutdown()


class MqttAdapter(Adapter):
    """MQTT 단독(백본 없음, Mosquitto 2.1.2). QoS1·영속 세션(V1 Telegraf#1 과 같은 조건).
    MQTT 는 저장된 과거를 다시 읽는 수단이 없다(retained = 마지막 1건) → 재생은 '시도하고 0건'을 기록."""
    name = "mqtt"
    topic_name = "sensor/telemetry/raw/<device>/<tag>"
    supports = {"replay_position": False, "replay_time": False, "partitions": 1}

    def __init__(self, a):
        self.host = a.bootstrap or "mosquitto"
        self.run = a.run_id
        self.errors = 0

    def _client(self, cid, clean):
        import paho.mqtt.client as mqtt
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, clean_session=clean, protocol=mqtt.MQTTv311)
        c.reconnect_delay_set(1, 2)
        c.max_inflight_messages_set(100)
        return c

    async def setup(self):
        self.p = self._client(f"bbpub-{self.run}", True)
        self.p.connect(self.host, 1883)
        self.p.loop_start()

    async def start_consumer(self, on_msg):
        ok = threading.Event()
        self.s = self._client(f"bbsub-{self.run}", False)
        self.s.on_connect = lambda c, u, f, rc, p=None: (c.subscribe("sensor/telemetry/raw/#", qos=1), ok.set())
        self.s.on_message = lambda c, u, m: on_msg(m.payload, {})
        self.s.connect(self.host, 1883)
        self.s.loop_start()
        ok.wait(30)
        await asyncio.sleep(1)

    async def send(self, key, payload):
        dev, _, tag = key.rpartition("/")
        info = self.p.publish(f"sensor/telemetry/raw/{dev or T.DEVICE0}/{tag}", payload, qos=1)
        if info.rc != 0:
            self.errors += 1

    async def flush(self):
        await asyncio.sleep(2)

    async def replay_time(self, t_ms, stop_when, timeout):
        got, ok = [], threading.Event()
        c = self._client(f"bbreplay-{uuid.uuid4().hex[:8]}", True)
        c.on_connect = lambda cl, u, f, rc, p=None: (cl.subscribe("sensor/telemetry/raw/#", qos=1), ok.set())
        c.on_message = lambda cl, u, m: got.append(m.payload)
        c.connect(self.host, 1883)
        c.loop_start()
        ok.wait(15)
        await asyncio.sleep(min(timeout, 10))
        c.loop_stop()
        c.disconnect()
        return got

    async def close(self):
        for c in (self.p, self.s):
            c.loop_stop()
            c.disconnect()


ADAPTERS = {"kafka": KafkaAdapter, "nats": NatsAdapter, "pulsar": PulsarAdapter, "rabbitmq-stream": RabbitStreamAdapter,
            "iggy": IggyAdapter, "rocketmq": RocketMQAdapter, "mqtt": MqttAdapter}


# ─────────────────────────────── run ───────────────────────────────
async def with_retry(fn, what, tries=60):
    for i in range(tries):
        try:
            return await fn()
        except Exception as e:
            last = e
            await asyncio.sleep(2)
    raise RuntimeError(f"{what} 실패: {last!r}")


async def run(a):
    out = RAW / f"{a.profile}_{a.variant}.json"
    RAW.mkdir(parents=True, exist_ok=True)
    if out.exists() and not a.overwrite:
        raise SystemExit(f"{out} 이미 있음 — --overwrite 또는 다른 variant")
    a.run_id = f"{a.profile}-{a.variant}-{uuid.uuid4().hex[:6]}"
    ad = ADAPTERS[a.adapter](a)
    t_setup = time.time()
    await with_retry(ad.setup, "setup")
    setup_s = round(time.time() - t_setup, 2)

    lock = threading.Lock()
    recv = []               # (key, seq, lat_ms, pos)
    first_pos_after_mid = {}
    state = {"mid_ns": None}

    def on_msg(payload, pos):
        now = time.time_ns()
        try:
            d = json.loads(payload)
        except Exception:
            return
        if d.get("run") != a.run_id:
            return
        k = T.key_of(d)
        with lock:
            recv.append((k, d["seq"], (now - d["emit_ns"]) / 1e6))
            if state["mid_ns"] and d["emit_ns"] >= state["mid_ns"]:
                pk = str(pos.get("p", 0))
                cand = pos.get("mid", pos.get("o", pos.get("seq")))
                if cand is not None and pk not in first_pos_after_mid:
                    first_pos_after_mid[pk] = cand
                elif cand is not None and not isinstance(cand, str):
                    first_pos_after_mid[pk] = min(first_pos_after_mid[pk], cand)

    await with_retry(lambda: ad.start_consumer(on_msg), "consumer")
    await asyncio.sleep(2)

    devs = T.devices(a.devices)
    ticks = int(a.duration * a.hz)
    t0 = time.time()
    sent = 0
    late_ticks = 0
    expected = {}
    by_key = {}           # key -> [(seq, ts_ns)]
    for i in range(ticks):
        target = t0 + i / a.hz
        d = target - time.time()
        if d > 0:
            await asyncio.sleep(d)
        elif d < -0.5:
            late_ticks += 1
        if i == ticks // 2:
            state["mid_ns"] = time.time_ns()
        for di, dev in enumerate(devs):
            for tag in T.TAG_NAMES:
                now = time.time_ns()
                r = T.record(tag, dev, now, i + 1, now, di)
                r["run"] = a.run_id
                k = T.key_of(r)
                await ad.send(k, T.encode(r))
                expected[k] = i + 1
                by_key.setdefault(k, []).append(r["emit_ns"])
                sent += 1
        if hasattr(ad, "flush_tick"):
            await ad.flush_tick()
    send_elapsed = time.time() - t0
    await ad.flush()
    deadline = time.time() + a.drain
    while time.time() < deadline and len({(k, s) for k, s, _ in list(recv)}) < sent:
        await asyncio.sleep(0.5)
    await asyncio.sleep(1)
    with lock:
        rs = list(recv)
    verdict = T.check_stream(expected, [(k, s) for k, s, _ in rs])
    lat = [x for _, _, x in rs]

    # 재생: 중간 시각 이후 기대 집합
    mid = state["mid_ns"]
    want = {(k, idx + 1) for k, lst in by_key.items() for idx, e in enumerate(lst) if e >= mid}

    def ids_of(got, cache={"n": 0, "ids": set(), "src": None}):
        if cache["src"] is not got:          # 새 재생 목록이면 캐시 초기화(증분 파싱)
            cache.update(n=0, ids=set(), src=got)
        for p in got[cache["n"]:]:
            try:
                d = json.loads(p)
            except Exception:
                continue
            if d.get("run") == a.run_id:
                cache["ids"].add((T.key_of(d), d["seq"]))
        cache["n"] = len(got)
        return cache["ids"]

    def stop_when(got):
        return len(ids_of(got) & want) >= len(want)

    def score(got):
        ids = set(ids_of(got))
        return {"expected": len(want), "matched": len(ids & want), "missing": len(want - ids),
                "extra_before_mid": len(ids - want), "ok": not (want - ids)}

    replay = {"supported": ad.supports}
    if ad.supports.get("replay_position"):
        try:
            got = await ad.replay_position(dict(first_pos_after_mid), stop_when, a.replay_timeout)
            replay["by_position"] = score(got) | {"start": first_pos_after_mid}
        except Exception as e:
            replay["by_position"] = {"ok": False, "error": repr(e)}
    else:
        replay["by_position"] = {"ok": False, "note": "클라이언트에 위치(오프셋) 지정 재생 수단 없음"}
    if ad.supports.get("replay_time") or a.adapter == "mqtt":
        try:
            got = await ad.replay_time(mid // 1_000_000 - 1000, stop_when, a.replay_timeout)
            replay["by_time"] = score(got) | {"t_ms": mid // 1_000_000 - 1000}
        except Exception as e:
            replay["by_time"] = {"ok": False, "error": repr(e)}
    await ad.close()

    res = {
        "exp": "EXP-BB", "stage": 2, "profile": a.profile, "adapter": a.adapter, "variant": a.variant, "run_id": a.run_id,
        "topic": ad.topic_name, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "load": {"devices": a.devices, "tags": 12, "hz": a.hz, "duration_s": a.duration,
                 "msg_per_s_target": 12 * len(devs) * a.hz, "sent": sent,
                 "msg_per_s_actual": round(sent / send_elapsed, 1), "late_ticks": late_ticks},
        "setup_s": setup_s, "send_errors": ad.errors,
        "delivery": verdict, "latency_ms": {"p50": T.pct(lat, .5), "p95": T.pct(lat, .95), "p99": T.pct(lat, .99),
                                            "max": T.pct(lat, 1.0), "n": len(lat)},
        "replay": replay, "restart_note": a.restart_note,
        "pass_stage2": verdict["lost"] == 0 and verdict["duplicates"] == 0 and verdict["reordered_within_key"] == 0
                        and ad.errors == 0,
        "guard": {"forced": os.environ.get("BENCH_GUARD_FORCED") == "1",
                  "rot_running": int(os.environ.get("BENCH_GUARD_ROT_RUNNING", "0"))},
    }
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps({k: res[k] for k in ("profile", "variant", "delivery", "latency_ms", "pass_stage2")}, ensure_ascii=False))


# ─────────────────────── Telegraf 1.40 호환(#17570) ───────────────────────
def telegraf_check(a):
    """전제: stage2.sh 가 telegraf-out·telegraf-in-v1cfg·telegraf-in-kver 를 띄워 둔 상태.
    out : 하니스 → telegraf-out(socket_listener) → outputs.kafka(V1 bridge 설정) → tg.out.raw → 하니스가 소비·모양 검사
    in  : 하니스 → Kafka sensor.telemetry.raw(V1 모양) → inputs.kafka_consumer(V1 sink 설정 그대로 / kafka_version 명시) → 파일"""
    import socket
    from confluent_kafka import Consumer, Producer
    bs = a.bootstrap or "kafka:9092"
    run = f"tg-{uuid.uuid4().hex[:6]}"
    n = 120
    # out — 확인용 토픽을 먼저 만든다(자동 생성이 꺼져 있어 없으면 "topic … does not exist" 로 쓰기 실패, #115)
    from confluent_kafka.admin import AdminClient, NewTopic
    ad = AdminClient({"bootstrap.servers": bs})
    if "tg.out.raw" not in ad.list_topics(timeout=30).topics:
        for fut in ad.create_topics([NewTopic("tg.out.raw", PARTITIONS, 1)]).values():
            try:
                fut.result(30)
            except Exception as e:
                if "TOPIC_ALREADY_EXISTS" not in str(e):
                    raise
        time.sleep(3)   # 텔레그래프 생산자가 새 메타데이터를 받도록
    s = socket.create_connection(("telegraf-out", 8094), timeout=30)
    base = time.time_ns()
    for i in range(n):
        tag = T.TAG_NAMES[i % 12]
        s.sendall(f'sensor,site=AR-100,device=reactor-line-01,tag={tag},quality=GOOD,run={run} value={T.value(tag, i)} {base + i * 1000}\n'.encode())
    s.close()
    c = Consumer({"bootstrap.servers": bs, "group.id": f"tgchk-{run}", "auto.offset.reset": "earliest"})
    c.subscribe(["tg.out.raw"])
    got, shape_ok, t0 = [], True, time.time()
    while time.time() - t0 < 40 and len(got) < n:
        m = c.poll(0.5)
        if m is None or m.error():
            continue
        d = json.loads(m.value())
        got.append(d)
        shape_ok &= set(d) == {"ts", "site", "device", "tag", "value", "quality"} and m.key() is not None
    c.close()
    # in
    p = Producer({"bootstrap.servers": bs, "acks": "all", "compression.type": "lz4"})
    now = time.time_ns()
    for i in range(n):
        r = T.record(T.TAG_NAMES[i % 12], T.DEVICE0, now + i * 1000, i + 1)
        r.pop("seq")
        r["device"] = f"tgin-{run}"
        p.produce(TOPIC, T.encode(r), key=r["tag"].encode())
    p.flush(30)
    time.sleep(15)
    counts = {}
    for name in ("in_v1cfg", "in_kver"):
        f = RAW / "telegraf" / f"{a.profile}_{name}.jsonl"
        k = 0
        if f.exists():
            for line in f.read_text(errors="replace").splitlines():
                if f"tgin-{run}" in line:
                    k += 1
        counts[name] = k
    res = {"output_kafka": {"sent": n, "received": len(got), "shape_v1": shape_ok and len(got) > 0},
           "input_kafka_consumer_v1_config": {"sent": n, "stored": counts["in_v1cfg"]},
           "input_kafka_consumer_kafka_version_set": {"sent": n, "stored": counts["in_kver"]},
           "issue": "https://github.com/influxdata/telegraf/issues/17570 (consume: EOF with Kafka 4, 워크어라운드 kafka_version)"}
    out = RAW / f"{a.profile}_telegraf.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps(res, ensure_ascii=False))


# ─────────────────────────────── summarize ───────────────────────────────
def summarize(a):
    runs = {}
    for f in sorted(RAW.glob(f"{a.profile}_*.json")):
        stem = f.stem[len(a.profile) + 1:]
        runs[stem] = json.loads(f.read_text())
    stats = {}
    for f in sorted(RAW.glob(f"stats_{a.profile}_*.csv")):
        by = {}
        with open(f) as fh:
            for row in csv.DictReader(fh):
                try:
                    by.setdefault(row["name"], {"cpu": [], "mem": []})
                    by[row["name"]]["cpu"].append(float(row["cpu_pct"]))
                    by[row["name"]]["mem"].append(float(row["mem_mib"]))
                except (ValueError, KeyError):
                    pass
        stats[f.stem.split("_", 2)[2]] = {n: {"cpu_pct_median": T.pct(v["cpu"], .5), "cpu_pct_p95": T.pct(v["cpu"], .95),
                                             "mem_mib_median": T.pct(v["mem"], .5), "mem_mib_max": T.pct(v["mem"], 1.0)}
                                         for n, v in by.items() if "client" not in n}
    meta = {}
    mf = RAW / f"images_{a.profile}.txt"
    if mf.exists():
        meta["images"] = mf.read_text().splitlines()
    core = [r for k, r in runs.items() if k in ("base", "x10", "scale")]
    res = {"exp": "EXP-BB", "stage": 2, "profile": a.profile, "runs": runs, "resources": stats, **meta,
           "stage2_verdict": ("통과" if core and all(r.get("pass_stage2") for r in core) and
                              all(r.get("replay", {}).get("by_time", {}).get("ok") or
                                  r.get("replay", {}).get("by_position", {}).get("ok") for r in core)
                              else "탈락 또는 미완(세부는 runs)") if core else "미실행",
           "note": "판정 규칙은 QUESTIONS.md §1. 이 파일은 ② 기동·기능 실측값이며 ③(3회 중앙값)·④(ROBUSTNESS)는 별도."}
    out = pathlib.Path(f"/experiments/EXP-BB/stage2_{a.profile}.json")
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"wrote {out} verdict={res['stage2_verdict']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "telegraf", "summarize"])
    ap.add_argument("--profile", required=True)
    ap.add_argument("--adapter", choices=list(ADAPTERS))
    ap.add_argument("--variant", default="base")
    ap.add_argument("--bootstrap")
    ap.add_argument("--admin")
    ap.add_argument("--devices", type=int, default=1)
    ap.add_argument("--hz", type=float, default=1.0)
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--drain", type=float, default=60)
    ap.add_argument("--replay-timeout", type=float, default=60)
    ap.add_argument("--restart-note")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args()
    if a.cmd == "run":
        asyncio.run(run(a))
    elif a.cmd == "telegraf":
        telegraf_check(a)
    else:
        summarize(a)


if __name__ == "__main__":
    main()
