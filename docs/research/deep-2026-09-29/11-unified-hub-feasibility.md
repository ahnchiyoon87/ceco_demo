# 11 · 통일 허브(UNS) 전환 가능성 — 문헌 조사

- 조사일: 2026-09-29
- 방식: 문헌만 조사함. 컨테이너·docker는 실행하지 않음.
- 원칙: 1차 출처(공식 문서, 릴리스 태그 소스, GitHub 이슈)만 적음. 확인 못 한 것은 [미확인]으로 적음.
- 대상 구조: 장치층 EdgeX 4.0.x(device-modbus) → MQTT 허브(Mosquitto 2.1.2 또는 RMQTT 0.24) → FUXA 1.3.4 구독 / 명령은 EdgeX core-command 경유 → Kafka 4.3(Bento 1.21.2) → Flink

(작성 중 — 절마다 추가함)

## 1 · FUXA 1.3.4 MQTT 클라이언트 장치

근거 소스: FUXA 태그 v1.3.4(릴리스 2026-08-12)의 `server/runtime/devices/mqtt/index.js`(617줄 전문 읽음), `device.js`, `device-utils.js`, `client/src/app/device/topic-property/topic-property.component.ts`.

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 태그↔토픽 대응 | 태그 하나의 `address`가 구독 토픽이다. 모든 태그의 address를 모아 `client.subscribe(topics)`로 한 번에 구독한다. 같은 토픽에 여러 태그를 묶을 수 있다(`topicsMap[topic]`이 배열). | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L368-L407 | 2026-09-29 |
| 와일드카드 토픽 | 수신 시 `topicsMap[topicAddr]`로 받은 토픽 문자열을 정확히 찾는다. 그래서 address에 `+`·`#`를 넣으면 구독은 되지만 태그에 값이 들어가지 않는다(코드 해석, 실행 미검증). | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L377-L379 | 2026-09-29 |
| 태그 형식 | 구독 태그 형식은 `raw`(메시지 전체 문자열)와 `json` 두 가지다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/client/src/app/device/topic-property/topic-property.component.ts#L243-L278 | 2026-09-29 |
| JSON 필드 추출 | `json` 태그는 `JSON.parse` 후 `subitems[memaddress]`로 **최상위 키 하나만** 읽는다. 중첩 경로·배열 검색(예: `readings[?resourceName=='TT-101'].value`)은 없다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L385-L396 | 2026-09-29 |
| 중첩 JSON 요청 | "MQTT JSON은 최상위 노드만 읽힌다, jsonpath 지원 요청" 이슈 #1092가 열린 상태다. | https://github.com/frangoteam/FUXA/issues/1092 | 2026-09-29 |
| 우회: 읽기 스케일 스크립트 | 태그 옵션의 `scaleReadFunction`(첫 인자 `value`인 서버 스크립트)이 원시값을 바꿔 돌려준다. MQTT 태그도 옵션 메뉴가 열린다(`isWithOptions`는 internal·WebCam만 false). 메인테이너가 #1155에서 "태그에 스크립트를 묶어 보라"고 답했다. EdgeX 이벤트 전체를 raw로 받아 스크립트에서 파싱하는 방식은 코드상 가능하나 실행은 미검증이다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/device-utils.js#L22-L57 · https://github.com/frangoteam/FUXA/blob/v1.3.4/client/src/app/device/device-list/device-list.component.ts#L133 · https://github.com/frangoteam/FUXA/issues/1155 | 2026-09-29 |
| QoS | `client.subscribe(topics, cb)`와 `client.publish(addr, payload, {retain:true})`에 qos를 주지 않는다. 동봉 mqtt.js 4.3.7의 기본값은 구독·발행 모두 QoS 0이다. UI에 QoS 설정은 없다(topic-property 소스에 qos 항목 없음). | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/package.json · https://github.com/mqttjs/MQTT.js/blob/v4.3.7/README.md | 2026-09-29 |
| 재접속 | `reconnectPeriod: 0`이라 mqtt.js 자동 재접속은 꺼져 있다. 대신 FUXA 장치 관리자가 5초(`DEVICE_CHECK_STATUS_INTERVAL = 5000`)마다 `isConnected()`를 보고 끊겼으면 INIT으로 돌려 다시 connect한다. 재접속 때 새 클라이언트로 다시 구독한다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L593-L609 · https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/device.js#L27 · https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/device.js#L181-L201 | 2026-09-29 |
| 세션·clientId | clientId는 보안 설정에 넣을 때만 지정된다. `clean` 옵션을 주지 않으므로 mqtt.js 기본(clean=true)이다(README 기본값 기준). 끊긴 동안의 메시지는 받지 못한다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L48-L66 · https://github.com/mqttjs/MQTT.js/blob/v4.3.7/README.md | 2026-09-29 |
| 값 반영 주기 | 메시지는 받자마자 메모리에만 넣고, 화면 전송·DAQ 저장은 장치 polling 주기(기본 3000ms, 장치 설정 `polling`)마다 한다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L150-L169 · https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/device.js#L29 | 2026-09-29 |
| 쓰기(발행) — 발행 태그 | 발행 태그(`options.pubs`)는 address 토픽으로 발행한다. 페이로드 항목 종류는 `value`(화면 입력값), `static`(고정 문자열), `timestamp`(ISO 시각), `tag`(다른 장치 태그 값)이다. `json` 형식이면 `{키: 값}` 평면 객체, `raw`면 값들을 `;`로 이어 붙인 문자열이다. 중첩 객체는 만들 수 없다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L540-L586 | 2026-09-29 |
| 쓰기 — 구독 태그 | 구독 태그에 값을 쓰면 **같은 구독 토픽**으로 발행한다(raw는 값 문자열, json은 `{memaddress: 값}`). | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L302-L327 · #L575-L581 | 2026-09-29 |
| retain 고정 | v1.3.4는 모든 발행에 `retain: true`를 고정한다. 명령에 retain이 붙으면 재접속·늦은 구독자가 옛 명령을 다시 받는다는 이슈 #2443(2026-07-17 등록)이 있다. retain 선택 PR #2518은 2026-09-08 master에 병합됐고 v1.3.4(2026-08-12)에는 없다. | https://github.com/frangoteam/FUXA/blob/v1.3.4/server/runtime/devices/mqtt/index.js#L543 · https://github.com/frangoteam/FUXA/issues/2443 · https://github.com/frangoteam/FUXA/pull/2518 | 2026-09-29 |
| 문서 | 공식 문서(HowTo Devices and Tags)는 "MQTT 연결과 토픽 구독 추가" 한 줄뿐이다. GitHub Wiki는 더 이상 관리하지 않는다고 적혀 있다. | https://frangoteam.github.io/FUXA/HowTo-Devices-and-Tags/ · https://github.com/frangoteam/FUXA/wiki | 2026-09-29 |

### 통일 구조에 주는 시사점(사실 근거만)

- EdgeX 이벤트 JSON(`readings` 배열 안의 `value`)을 FUXA `json` 태그로 바로 읽을 수 없다. 최상위 키만 읽기 때문이다.
- 방법은 둘이다. (가) 허브에 "태그당 토픽, 값만 담은 평면 페이로드"를 따로 발행한다(ASC·Bento 등 변환 필요, 2·5절 참조). (나) raw 태그 + 읽기 스케일 스크립트로 파싱한다(코드상 가능, 미검증).
- 와일드카드 한 번 구독으로 여러 태그를 채우는 방식은 코드상 동작하지 않는다. 태그마다 정확한 토픽이 필요하다.
- v1.3.4에서 FUXA가 MQTT로 명령을 발행하면 항상 retain=true·QoS 0이다. 명령 토픽에 retain이 남으면 재시작 때 명령이 다시 실행될 위험이 있다(#2443). 명령을 MQTT로 보낼 경우 브로커 쪽 retain 제거 또는 retain을 쓰지 않는 경로(REST, 3절)를 따져야 한다.
- EdgeX 명령 요청은 정해진 봉투 형식이 필요하다(3절). FUXA 발행 페이로드는 평면 JSON만 되므로 봉투 형식을 맞출 수 있는지는 3절 결과로 판단한다.
- 끊겼다가 붙으면 최대 약 5초 뒤 재접속한다. clean 세션이라 끊긴 사이 값은 잃고, retain된 최신값이 있으면 재구독 때 받는다(브로커 retain 동작 기준).

### 확인 못 한 것

- [미확인] 스케일 스크립트로 EdgeX 이벤트를 파싱했을 때 실제 동작·성능(실행 안 함).
- [미확인] FUXA 서버 스크립트 외 "Node-RED 연동" 경로로 변환하는 방법의 동작.
- [미확인] v1.3.4 이후 릴리스에 #2518이 포함됐는지(2026-09-29 기준 최신 릴리스는 v1.3.4).

