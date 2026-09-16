# 1. PDF 분석과 사전 기술 실사

> 교재 활용: **1차시 — 아키텍처 문서를 어떻게 검토할 것인가**

## 1.1 출발점

입력은 PDF 한 편이었습니다.

```bash
pdfinfo "IoT SCADA 파이프라인 아키텍처.pdf"
# Pages: 15
pdftotext -layout "IoT SCADA 파이프라인 아키텍처.pdf" scada.txt
# 625 lines
```

PDF 가 권고한 스택:

```
센서/PLC ─Modbus/OPC-UA─▶ EdgeX ─MQTT─▶ EMQX ──▶ Kafka ──▶ Flink ──▶ InfluxDB ──▶ Grafana
                                                              +ONNX              FUXA
                                                                                 Prometheus
```

그리고 5개의 결론:

1. IoT 미들웨어 존치 (EdgeX / EMQX)
2. Esper → Flink CEP 대체
3. 선택적 결측치 보간 (ML 경로에만)
4. 인라인 ML 추론 서빙 (ONNX 임베디드)
5. 저장소·시각화 이원화 (InfluxDB/Prometheus, FUXA/Grafana)

---

## 1.2 사전 실사: 구현 전에 확인해야 할 것

**교육 포인트**: 아키텍처 문서는 "무엇을 쓸지" 를 말하지만 "그게 실제로 되는지" 는
말하지 않습니다. 코드를 쓰기 전에 다음 세 가지를 확인해야 합니다.

1. 그 기능이 **오픈소스 판에 실제로 있는가**
2. 그 이미지가 **내 아키텍처(arm64/amd64)를 지원하는가**
3. 그 라이브러리가 **내 런타임에서 빌드되는가**

### 실사 1 — 이미지 아키텍처

```bash
for img in frangoteam/fuxa:latest emqx/emqx:5.8.6 apache/kafka:3.9.0 \
           flink:1.20-scala_2.12-java17 influxdb:2.7 grafana/grafana:11.4.0 \
           telegraf:1.33 edgexfoundry/device-modbus:4.0.0; do
  printf "%-45s " "$img"
  docker manifest inspect "$img" | grep -o '"architecture": "[a-z0-9]*"' | sort -u | tr '\n' ' '
  echo
done
```

결과: **전부 arm64 지원**. 이 단계에서 막혔다면 설계를 바꿔야 했을 것입니다.

### 실사 2 — EMQX 의 Kafka Sink

PDF p.10 은 "EMQX 의 데이터 통합 브리지를 통해 Kafka 토픽으로 적재" 를 전제합니다.
그런데 EMQX 문서의 Kafka 연동 페이지는 전부 **Enterprise** 경로에 있습니다.

```
https://docs.emqx.com/en/enterprise/v5.1/data-integration/data-bridge-kafka.html
                          ^^^^^^^^^^
```

**결론: EMQX OSS 5.x 에는 Kafka 프로듀서 커넥터가 없습니다.**
Rule Engine 은 있지만 싱크로 Kafka 를 고를 수 없습니다.

> **교육 포인트**: "X 가 Y 를 지원한다" 는 서술을 만나면 그것이
> 커뮤니티 판인지 상용 판인지 확인해야 합니다. IIoT 스택은 특히
> 오픈코어 모델이 많아 이 함정이 잦습니다.

### 실사 3 — PyFlink 의 arm64 지원

PDF 는 "Flink 내부에 ONNX Runtime 임베디드" 를 권고합니다.
Python 으로 하려면 PyFlink 가 필요합니다.

```bash
curl -s https://pypi.org/pypi/apache-flink/json | python3 -c "
import json,sys
d=json.load(sys.stdin)
for rel in ['1.20.1','2.0.0']:
    fs=d['releases'].get(rel,[])
    print(rel, sorted({f['filename'].split('-')[-1] for f in fs}))
"
```

```
1.20.1 ['1.20.1.tar.gz', 'macosx_10_9_x86_64.whl',
        'macosx_11_0_arm64.whl', 'manylinux1_x86_64.whl']
```

**linux-aarch64 휠이 없습니다.** macOS arm64 용은 있지만 리눅스 arm64 용은 없어서,
Apple Silicon 의 linux/arm64 컨테이너에서는 소스 tarball 로 떨어져 빌드에 실패합니다.

### 실사 4 — 대안의 타당성 확인

Java + `com.microsoft.onnxruntime` 로 가기로 하고, 그 JAR 에 네이티브가 있는지 확인:

```bash
curl -sL -o ort.jar "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime/1.20.0/onnxruntime-1.20.0.jar"
unzip -l ort.jar | grep -E "\.(so|dylib|dll)$"
```

```
ai/onnxruntime/native/linux-aarch64/libonnxruntime.so      (13,648,160 bytes)
ai/onnxruntime/native/linux-aarch64/libonnxruntime4j_jni.so   (133,256 bytes)
ai/onnxruntime/native/linux-x64/libonnxruntime.so         (16,551,224 bytes)
...
```

**있습니다.** 게다가 이 JNI 는 C++ 네이티브를 감싸므로, PDF 가 말한
"C++ 기반 ONNX Runtime 임베디드" 에 **PyFlink 보다 더 정확히 부합**합니다.

---

## 1.3 실사 결과 요약

| 항목 | PDF 전제 | 실사 결과 | 조치 |
|---|---|---|---|
| 이미지 arm64 | (언급 없음) | 전부 지원 | 그대로 진행 |
| EMQX Kafka Sink | OSS 로 가능 | **Enterprise 전용** | Telegraf 브리지로 대체 |
| PyFlink ONNX | 가능 | **arm64 휠 없음** | Java + onnxruntime JNI |
| onnxruntime Java arm64 | – | 네이티브 포함 확인 | 채택 |

이 4가지를 **코드 한 줄 쓰기 전에** 확인한 것이 이 프로젝트에서 가장 큰
시간 절약이었습니다. 특히 2·3번을 모르고 구현했다면 Tier-2/Tier-3 를
통째로 다시 만들어야 했을 것입니다.

---

## 1.4 실습 과제 (교재용)

1. 여러분의 조직이 쓰는 오픈소스 중 "오픈코어" 모델인 것을 3개 찾고,
   커뮤니티 판에서 빠진 기능을 정리하시오.
2. 사내 표준 컨테이너 이미지 목록에 대해 `docker manifest inspect` 로
   arm64 지원 현황표를 만드시오.
3. PDF 의 결론 5개 중 하나를 골라, 그것이 "실제로 가능한지" 를 확인하는
   명령을 작성하시오.
