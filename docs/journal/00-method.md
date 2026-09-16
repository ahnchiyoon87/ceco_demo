# 작업 방법론

## 기본 원칙: 추측하지 말고 확인한다

이 프로젝트에서 반복적으로 효과를 본 습관 하나가 있습니다.
**문서나 기억에 의존하지 않고, 대상 시스템의 실제 산출물을 먼저 확인하는 것**입니다.

구체적으로:

| 상황 | 하지 않은 것 | 한 것 |
|---|---|---|
| EdgeX 구성 | 기억/블로그 기반 compose 작성 | 공식 `docker-compose-no-secty.yml` 다운로드 후 정의 확인 |
| EdgeX 설정 키 | 문서에서 키 이름 추정 | core-keeper KV 를 직접 조회해 실제 키 경로 확인 |
| FUXA 프로젝트 스키마 | JSON 구조 추정 | `project.demo.fuxap` 를 받아 실제 구조 파싱 |
| FUXA Modbus 주소 | Modbus 표준대로 0-based 가정 | 드라이버 소스(`modbus/index.js`)에서 `address - 1` 확인 |
| 라이브러리 아키텍처 지원 | "아마 되겠지" | PyPI API / `docker manifest inspect` / `unzip -l` 로 확인 |

이 습관 덕분에 **구현 전에** 두 개의 치명적 가정 오류를 잡았습니다.
(EMQX Kafka Sink 가 Enterprise 전용 / PyFlink 에 arm64 휠 없음)

반대로 이 습관을 건너뛴 곳에서 시간을 잃었습니다.
FUXA 의 코일 `memaddress` 를 `"0"` 으로 **추측**해서 넣었고,
`Cannot read properties of undefined (reading 'Items')` 라는 불친절한 오류를
소스를 읽고서야 해결했습니다.

---

## 검증 우선 순서: 위험한 것부터

구현 순서는 "쉬운 것부터" 가 아니라 **"틀리면 설계가 무너지는 것부터"** 로 잡았습니다.

```
1순위  onnxruntime Java 에 linux-aarch64 네이티브가 있는가?
       → 없으면 Tier-3 설계 전체를 다시 해야 함
       → unzip -l 로 30초 만에 확인 (있었음)

2순위  EdgeX 4.0 이 arm64 에서 기동되는가?
       → 가장 컴포넌트가 많고 깨지기 쉬움

3순위  FUXA 프로젝트를 REST 로 주입할 수 있는가?
       → 불가능하면 "설정만으로 동작" 목표가 무너짐
       → 소스에서 POST /api/project 확인
```

---

## 계층별 단계 검증

Tier 1 → 2 → 3 → 4 순으로 쌓되, **각 계층을 완성한 직후 실제로 데이터를 흘려보고**
다음으로 넘어갔습니다. 한꺼번에 만들어 놓고 통합하면 29개 컨테이너 중
어디가 문제인지 좁히는 데만 몇 배의 시간이 듭니다.

각 계층의 "완료" 기준은 눈으로 본 증거였습니다.

| 계층 | 완료 기준 |
|---|---|
| Tier 1 | Modbus 읽기값 = REST `/state` 값, 코일 쓰기 시 유량이 0이 됨 |
| Tier 2 | Kafka 토픽에서 정확한 스키마의 메시지를 꺼내 봄 |
| Tier 3 | Flink 잡 4개 RUNNING + 각 토픽 오프셋 증가 확인 |
| Tier 4 | InfluxDB 쿼리 결과, Grafana 데이터소스 응답, FUXA 쓰기→물리 반응 |

---

## "성공했다는 보고"를 믿지 않기

가장 값진 교훈 하나. 잡 제출 스크립트가 **"✓ Tier-1 SQL 제출 완료"** 를 출력했는데
실제로는 잡이 하나도 생성되지 않은 일이 있었습니다.

원인은 sql-client 출력에 ANSI 색상코드가 섞여 `grep "^\[ERROR\]"` 가
매칭되지 않은 것이었습니다. 그래서 **텍스트가 아니라 상태를 검증**하도록 바꿨습니다.

```bash
# 이전 — 텍스트를 믿음
sql-client.sh -f x.sql | grep -q "ERROR" && exit 1
echo "✓ 제출 완료"

# 이후 — 실제 잡 수를 셈
sql-client.sh -f x.sql 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' > log
grep -qE "^\[ERROR\]" log && exit 1
submitted=$(grep -c "^Job ID:" log)
[ "$submitted" -lt 3 ] && exit 1
running=$(curl -s "$JM/jobs/overview" | grep -o '"state":"RUNNING"' | wc -l)
[ "$running" -lt 4 ] && exit 1
```

같은 원칙을 모델 학습에도 적용했습니다. "학습 완료 (val loss 0.0196)" 만으로는
모델이 쓸모 있는지 알 수 없어서, **학습 직후 판별력 자가검증**을 파이프라인에
넣었습니다. 그리고 그 검증이 실제로 첫 모델이 무용지물임을 잡아냈습니다
(정상 오탐 49% / drift 탐지 43.9%).

---

## 도구

| 목적 | 도구 |
|---|---|
| PDF 텍스트 추출 | `pdftotext -layout` |
| 이미지 아키텍처 확인 | `docker manifest inspect ... \| grep architecture` |
| 파이썬 휠 플랫폼 확인 | PyPI JSON API |
| JAR 내용 확인 | `unzip -l` |
| 컨테이너 내부 소스 읽기 | `docker exec ... sed -n 'N,Mp' file` |
| Kafka 처리량 측정 | `kafka-get-offsets.sh` (컨슈머보다 정확·빠름) |
| 서비스 간 통신 확인 | `docker run --rm --network iiot curlimages/curl` |
