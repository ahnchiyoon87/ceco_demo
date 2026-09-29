# 16 · 외부 시스템 연결 — 밖으로 보내기와 설비 쪽으로 보내기

> 완료 (2026-09-30) (2026-09-30 작성 시작). 절을 끝낼 때마다 아래에 덧붙인다.

- 의뢰서: `docs/research/DEEP_RESEARCH_BRIEF_2026-09-29.md` §1·§3·§5·§9 읽음. 12번(§1-B·§1-C·§4-3·§5 포함 전문), 13번(A·B절 전문, F~J·확인 못 한 것), 14번(최종 표, B5·B6) 읽음.
- 확인일: 적힌 모든 출처 2026-09-30. 문헌 조사만 했다. docker·컨테이너는 건드리지 않았다. 이 파일 말고는 고치지 않았다.
- 근거 표시: [표준] 표준·공공 지침 / [독립] 독립 분석가·학술·SI / [벤더 홍보] 벤더 글·문서·벤더가 한 설문 / [공개 사례] 이름 있는 기업·현장 / [재단] 재단·오픈소스 문서. "(원문 확인)" = 페이지를 직접 읽음. "(검색 발췌)" = 검색 요약만 봄. "(12번 확인)" 등 = 앞 조사에서 확인한 것, 다시 조사 안 함. 추론은 "판단:"으로 따로 쓴다.
- 이번에 새로 찾은 가장 중요한 공공 근거: **NCSC-UK·CISA·FBI·BSI 외 8개 기관 「Secure connectivity principles for OT」(2026-01-14, 33쪽)** — https://www.ic3.gov/CSA/2026/260114.pdf (PDF 본문 추출해 원문 확인). 이하 "OT 연결 원칙 2026"이라 부른다.

---

## 1. 밖으로 보내는 방법 — 빠짐없이 나열 (설비 데이터 → 외부)

먼저 공통 규칙(이미 확인): DMZ를 거친다, OT 쪽이 연결을 연다(밀어낸다), IT → OT 직접 경로 없음 (12번 §1-B 확인: NIST SP 800-82r3, CISA DiD 2016, CISA AI-OT 2025).
이번에 더 강한 문장을 찾았다.
- "All connections with the OT environment should be initiated as outbound connections from within the OT environment." 바깥이 OT 자산에 접근해야 하면 DMZ의 중개 게이트웨이(brokered connection)를 쓴다. [표준] OT 연결 원칙 2026 p.11 (원문 확인)
- "External connections for data exchange between OT and IT should be brokered through a DMZ and use secure, standardised protocols designed for interoperability (such as OPC UA over TLS, MQTT over TLS, HTTPS). Where operational data needs to be shared, replicate the OT historian to a historian instance in the DMZ via a unidirectional, secure transfer mechanism, ensuring no inbound connectivity from IT to OT. IT systems should query the DMZ historian via a secure HTTP-based API with strong authentication, rather than directly accessing OT systems." [표준] 같은 문서 p.19 (원문 확인)
- "Where possible, establish outbound only uni-directional connectivity" [표준] 같은 문서 p.22 (원문 확인)

| # | 방법 | 전형적 흐름(어느 층 → 어느 층, 누가 연결을 여나) | 표준·근거 | 근거 종류 |
|---|---|---|---|---|
| O1 | **히스토리언 복제(사이트 → DMZ) + 기업 히스토리언** | OT L3 사이트 히스토리언 → (단방향 전송) → DMZ 복제 히스토리언 → IT 사용자·앱은 DMZ 히스토리언을 HTTP API로 조회. 연결은 OT 쪽이 연다. 기업 히스토리언(본사·클라우드)은 DMZ 사본에서 다시 받는다. | OT 연결 원칙 2026 p.19 (원문 확인) / CISA DiD 2016 §2.4.2 (12번 확인) / AVEVA 문서 "Configure replication to AVEVA PI server"(AVEVA Historian → PI 복제 설정) https://docs.aveva.com/bundle/sp-historian/page/909350.html (검색 발췌) | [표준] + [벤더 홍보] |
| O2 | **데이터 다이오드·단방향 게이트웨이** | O1·O4의 경계 장치로 쓴다. 하드웨어가 방향을 강제한다. 다이오드 벤더는 히스토리언(PI 등)·OPC DA·Modbus·S7용 복제 소프트웨어를 같이 판다. | NIST 800-82r3 §5.2.3.1 (12번 확인) / OT 연결 원칙 2026 p.22: 다이오드는 "방향만" 보장하고 Cross Domain 솔루션의 다른 보안 기능을 대신하지 않는다. **"a diode in each direction (to enable bi-directional communications such as APIs) … is considered an anti-pattern."** p.32: 격리 중에도 다이오드로 텔레메트리·로그 전송은 유지할 수 있다 (원문 확인) / Waterfall "Waterfall for AVEVA PI" (검색 발췌) | [표준] + [벤더 홍보] |
| O3 | **NAMUR NOA 두 번째 채널(보안 게이트웨이 + 집계 서버)** | 공정 제어(CPC) → NE 177 보안 게이트웨이(단방향) → NE 179 집계 서버 → M+O 앱. 주 제어 경로와 따로 흐른다. OPC UA(NE 176 정보 모델) 기반. | NE 177: "unidirectional data flow without any feedback path"(NAMUR 페이지, 게시일 표기 04/12/2021) https://www.namur.net/en/publications/news-archive/ne-177-is-newly-published.html (원문 확인) / NE 175·176·179 (12번 확인) / NE 179 집계 서버가 여러 다이오드 선을 하나의 인터페이스로 묶는다는 해설 (검색 발췌) | [표준]·업계 권고 |
| O4 | **OPC UA Client/Server, PubSub, 집계(Aggregation) 서버** | ① Client/Server: 제어기·SCADA가 OPC UA 서버, 엣지·히스토리언·MES가 클라이언트(구독). 경계에서는 DMZ의 집계 서버·게이트웨이가 받는다. ② PubSub(Part 14): 브로커(MQTT)로 JSON·UADP 메시지를 발행 → 클라우드 분석. BrokerTransportQoS가 MQTT QoS 0/1/2에 대응. | OPC UA Part 14 §7.3.4/7.3.5 MQTT 전송 https://reference.opcfoundation.org/specs/OPC-10000-14/7.3.4 (검색 발췌) / OT 연결 원칙 2026 p.19 "OPC UA over TLS" (원문 확인) / p.18 "OPC DA to OPC UA"로 옮기라 (원문 확인) / 13번 A1(구독·deadband) 확인 | [재단] + [표준] |
| O5 | **MQTT·UNS·Sparkplug (브로커 브리지)** | 엣지 → 사이트 브로커(UNS) → (브리지, OT가 `out` 연결) → DMZ·기업·클라우드 브로커. Sparkplug Host Application(SCADA·히스토리언·MES)이 구독. | 12번 §1-F, 13번 A6·G1 확인 / OT 연결 원칙 2026 p.19 "MQTT over TLS" (원문 확인) / HiveMQ Edge "backhaul" 브리지 (13번 I1 확인) | [재단]·[표준]·[벤더 홍보] |
| O6 | **이벤트 스트리밍(Kafka 등)** | UNS 브로커 → (브로커 안 Kafka 확장 = 밀어냄 / Kafka Connect MQTT Source = 끌어감 / 엣지 게이트웨이 브리지) → Kafka → 분석·저장·클라우드. PLC4X Kafka Source처럼 PLC에서 직접 Kafka로 넣는 커넥터도 있다. | 13번 A6 확인(세 방식 공존) / IoT Analytics 2026-01-28 "UNS is now maturing beyond just MQTT connectivity … vendors are leveraging high-throughput backends (such as Kafka and NATS)" https://iot-analytics.com/top-10-industrial-automation-trends/ (원문 확인) / Apache PLC4X Kafka 커넥터 https://plc4x.apache.org/plc4x/latest/users/integrations/apache-kafka.html (원문 확인) | [독립] + [재단] + [벤더 홍보] |
| O7 | **벤더 클라우드 커넥터·엣지 플랫폼** | 엣지 게이트웨이(현장) → 클라우드 자산 모델·시계열 서비스. 예: AWS IoT SiteWise Edge(OPC UA 소스 수집 → 클라우드 자산 모델), Azure IoT Operations(층별 브로커 → 클라우드). 연결은 엣지가 연다. | AWS 문서 "OPC UA data sources for AWS IoT SiteWise Edge gateways" https://docs.aws.amazon.com/iot-sitewise/latest/userguide/configure-sources-opcua.html (검색 발췌) / Azure 계층 자습서 (12번 확인) | [벤더 홍보] |
| O8 | **파일·REST·DB 배치 (ISA-95 B2MML 포함)** | ① MES → ERP 생산 실적·재고 보고: ISA-95 Part 5 거래를 B2MML(XML) 또는 B2MML-JSON으로. SOAP·REST·메시지 큐. ② IT 앱이 DMZ 히스토리언을 HTTP API로 조회(O1). ③ CSV·DB 내보내기. | MESA B2MML "XML implementation of the ANSI/ISA-95 … set of XML schemas" https://github.com/MESAInternational/B2MML-BatchML (검색 발췌) / MESA 블로그: B2MML-JSON이 Part 5 거래 전부 포함, "JSON은 보통 REST, XML은 SOAP" https://blog.mesa.org/2021/01/b2mml-json-version-available-from-mesa.html (검색 발췌) / OT 연결 원칙 2026 p.19 HTTP API (원문 확인) / CSV·DB 배치의 표준·근거 문서: **찾지 못함** | [표준]·[재단] |
| O9 | **SCADA 자체 연계** | SCADA 서버가 자기 OPC UA 서버·MQTT 발행 모듈·DB 기록(store-and-forward) 기능으로 위에 낸다. | Cirrus Link(Ignition MQTT 모듈) (13번 B1 확인) / Ignition Store and Forward (13번 A5 확인) | [벤더 홍보] |
| O10 | **DataOps 플랫폼 + 표준 조회 API (새로 나옴)** | 맥락화된 데이터 플랫폼(UNS·히스토리언 위)에 공통 API를 두고 앱이 조회·구독. CESMII i3X: 네임스페이스·객체 종류 탐색, 현재값·이력 조회, 변경 구독, "Update current and historical data (where permitted)". 2026-04-20 베타 발표, 1.0 출시(날짜는 페이지에 없음), 40개+ 공급사 지지. | https://www.i3x.dev/ (원문 확인) / https://www.cesmii.org/i3x-beta-launch/ (원문 확인) / 1.0·40개 공급사 https://www.manufacturingusa.com/news/cesmii-releases-i3xtm-10-complete-implementation-ready-open-api-specification-manufacturing (검색 발췌) | [재단](CESMII는 미국 제조 혁신 연구소) |

판단:
- 표준 문서가 **이름을 들어 권하는** 밖으로 보내기 방법은 O1(DMZ 히스토리언 복제 + HTTP API 조회), O2(단방향), O3(NOA 두 번째 채널), O4·O5의 보안 프로토콜(OPC UA over TLS, MQTT over TLS, HTTPS)이다. O6(Kafka)·O7(벤더 클라우드)·O10(i3X)은 표준 지침이 아니라 분석가·재단·벤더 자료에 나온다.
- 모든 방법에 공통인 모양은 **"OT가 밀어내고, 바깥은 DMZ에 있는 사본·중개자를 읽는다"** 이다.

---

## 2. 방법별 현업 사용 정도

결론 먼저: **방법별 사용률을 한 설문에서 나란히 잰 독립 자료는 찾지 못함.** 있는 수치는 프로토콜 선호, 투자 순위, 재단의 자기 발표뿐이다. 벤더가 한 설문은 [벤더 홍보]로 표시한다.

| 방법 | 찾은 수치 | 근거 종류·출처 | 판정 |
|---|---|---|---|
| O1 히스토리언 복제 | 사용률 수치 **찾지 못함.** 다이오드 벤더가 "가장 안전한 PI·AVEVA Data Hub 사이트는 대개 IT/OT 경계에 단방향 게이트웨이를 최소 한 층 쓴다"고 쓴다. 시장조사 사이트의 "제조 62%가 히스토리언 도입" 같은 수치는 방법을 확인 못 해 쓰지 않는다. | [벤더 홍보] https://waterfall-security.com/ot-insights-center/ot-cybersecurity-insights-center/unidirectional-gateways-the-strongest-and-most-agile-security-for-aveva-pi-systems/ (검색 발췌) | 수치 없음. 공공 지침 두 개(CISA 2016, OT 연결 원칙 2026)가 권하는 기본형 |
| O2 데이터 다이오드 | 도입률 **찾지 못함.** SANS 2025 ICS/OT 설문(330명) 공개 요약에는 자산 가시성 50%, MFA 원격 접속 47%, 제로트러스트·망 구획 32%만 있고 다이오드 항목은 없다. | [독립] SANS 2025 요약 https://www.sans.org/white-papers/state-of-ics-ot-security-2025 (검색 발췌) | 수치 없음 |
| O3 NAMUR NOA | 도입률 **찾지 못함.** 공정 산업 권고로 발행(NE 175~179). | [표준]·업계 권고 (12번 확인) | 공정 산업 한정, 수치 없음 |
| O4 OPC UA | 재단 자기 발표: "5,200개 넘는 공급사, 42,000개 넘는 OPC 제품, 5,200만 개 넘는 적용"(OPC 전체, UA만이 아님). HiveMQ·IIoT World 2025 설문: "OPC UA와 Modbus가 기계 통신 선호 프로토콜". | [재단] 자기 발표 (검색 발췌) / [벤더 홍보] https://www.hivemq.com/blog/expanding-industrial-iot-in-2025-survey-reveals-growth/ (원문 확인, 해당 비율 수치는 글에 없음) | 기계 쪽 연결의 주류라는 근거는 여럿. 밖으로 보내는 용도의 비율은 없음 |
| O5 MQTT·Sparkplug | HiveMQ·IIoT World 2024 설문(350명, 2024-01): "60%가 MQTT를 IIoT 프로토콜로 선택". Sparkplug는 "25%가 배포했거나 검토 중"(검색 발췌). 2025판: "MQTT와 HTTP가 계속 선호 IIoT 프로토콜", "Sparkplug는 소폭 증가". Eclipse IoT 개발자 설문 MQTT 49~56% (14번 확인). | [벤더 홍보] https://www.hivemq.com/blog/building-industrial-iot-systems-2024/ (원문 확인) / 2025판 (원문 확인) / [재단] Eclipse (14번 확인) | MQTT는 여러 설문에서 1위. 단 두 설문 모두 MQTT 관련 단체가 했다 |
| O6 Kafka | 제조 한정 사용률 **찾지 못함.** 일반 개발자 설문 Stack Overflow 2024 Kafka 9.4% (14번 확인). 독립 분석가가 "UNS 백엔드로 Kafka·NATS를 쓰는 벤더가 늘었다"고 적음(정성). | [독립] (14번 확인) / [독립] IoT Analytics 2026-01-28 (원문 확인) | 제조 수치 없음, 늘어나는 방향이라는 정성 근거만 |
| O7 벤더 클라우드 | Rockwell 2025 State of Smart Manufacturing(1,500곳 넘는 제조사, 17개국, 2025-03 조사): "클라우드/SaaS와 AI가 투자 1·2위". 연결 방식 비율은 없다. | [벤더 홍보] Rockwell 보도자료 https://www.rockwellautomation.com/en-us/company/news/press-releases/Ninety-Five-Percent-of-Manufacturers-Are-Investing-in-AI-to-Navigate-Uncertainty-and-Accelerate-Smart-Manufacturing.html (검색 발췌) | 투자 의향만, 연결 방식 비율 없음 |
| O8 파일·REST·DB, B2MML | "주요 ERP·MES 벤더가 모두 B2MML을 지원한다"는 문장은 해설 사이트에만 있다. 수치 **찾지 못함.** HiveMQ 2024 설문의 "HTTP 58%가 필수 데이터 이동 도구"는 검색 발췌뿐. | (검색 발췌) | 수치 없음 |
| O9 SCADA 자체 연계 | **찾지 못함.** | — | 수치 없음 |
| O10 i3X 등 표준 API | 2026년 발표. 지지 공급사 "40개 넘음"(재단 발표). 도입 사례 수치 없음. | [재단] (검색 발췌) | 초기 단계 |
| (참고) 통합 데이터 모델 | Deloitte 2025: "통합 데이터 모델로 데이터 표준을 갖췄다" 54%, "아키텍처 표준을 쓴다" 45%. UNS 문항은 없음. | [독립] (12번 확인) | 방법별 수치 아님 |

판단: "밖으로 보내는 방법"의 현업 비율은 공개 자료로는 **말할 수 없다.** 확실히 말할 수 있는 것은 두 가지다. ① 공공 지침(CISA 2016, OT 연결 원칙 2026)이 **DMZ 히스토리언 복제 + 단방향**을 권장 기본형으로 이름까지 들어 적는다. ② MQTT는 여러 설문에서 IIoT 프로토콜 1위이고, OPC UA는 기계 쪽 연결의 선호 프로토콜이다(설문 주체가 관련 업체라는 한계).

---

## 3. 2026 추세 — 무엇이 늘고 무엇이 줄고 있나

| 방향 | 원문 문장(인용) | 출처·근거 종류 |
|---|---|---|
| 늘어남: UNS 뒤 고처리량 백엔드(Kafka·NATS), 실시간+이력 결합 | "UNS is now maturing beyond just MQTT connectivity. As the industrial DataOps space matures, vendors are leveraging high-throughput backends (such as Kafka and NATS), integrating historical data with real-time streams, and introducing architectural modularity." | [독립] IoT Analytics, Anand Taparia, 2026-01-28 https://iot-analytics.com/top-10-industrial-automation-trends/ (원문 확인) |
| 늘어남: 산업 DataOps 업체 | 12대 추세 6번 제목 "Industrial DataOps vendors experiencing rapid commercial growth" | [독립] IoT Analytics, 2026-06-22 https://iot-analytics.com/top-industrial-technology-trends/ (원문 확인) |
| 늘어남: AI가 실행까지 하려는 흐름, 그러나 데이터 기반이 못 따라옴 | "The industry is moving away from AI models that merely provide textual suggestions toward autonomous systems capable of executing complex workflows." / "A central tension is emerging: Vendors are starting to monetize autonomous AI decision-making on the shop floor before many manufacturers have solved the trusted, contextualized data foundation needed to execute those decisions safely." / 9번 "Digital twins evolving toward AI-driven, closed-loop executable environments" | [독립] 같은 글 (원문 확인) |
| 늘어남: 에이전트는 사람 승인 아래 | "Vendors advancing generative AI (GenAI) toward autonomous agents" … Schneider Electric 시연은 에이전트가 자산을 만들고 "letting the user approve the creation" | [독립] IoT Analytics 2026-01-28 (원문 확인) |
| 늘어남: 공통 조회 API | CESMII i3X 베타(2026-04-20) → 1.0. "manufacturing data silo proliferation and API chaos"를 풀려는 공통 API | [재단] (원문 확인, 1.0은 검색 발췌) |
| 줄여야 함(공공 지침): 안으로 들어오는 연결, 오래된 프로토콜 | "All connections with the OT environment should be initiated as outbound connections from within the OT environment." / "Default to the latest secure versions of industrial protocols (e.g. DNP3 to DNP3-SAv5, CIP to CIP Security, Modbus to Modbus Security, OPC DA to OPC UA)." / 분석·업무 시스템은 "observe and analyse, not command or alter operations" | [표준] OT 연결 원칙 2026 p.11, p.18, p.25 (원문 확인) |
| 소폭 증가: Sparkplug | "MQTT Sparkplug saw a marginal growth in adoption." | [벤더 홍보] HiveMQ·IIoT World 2025 (원문 확인) |
| 줄어드는 것의 **독립 수치** | 특정 방법(예: 파일 배치, 직접 폴링)이 줄었다는 독립 분석가 문장은 **찾지 못함.** ARC Advisory의 i3X 분석 글은 403으로 읽지 못함. LNS Research는 "Industrial DataOps" 평가 틀을 내놓았다는 것만 확인(검색 발췌). | ARC https://www.arcweb.com/blog/beyond-decoupling-how-cesmiis-i3x-solves-context-engineering-gap-industrial-data-fabrics (접속 거부) / LNS https://blog.lnsresearch.com/topic/industrial-dataops (검색 발췌) |

판단: 2026년에 **느는 쪽**은 "UNS(MQTT) 뒤에 Kafka·NATS 같은 장부를 붙이고, 그 위에 DataOps·공통 API를 얹는" 모양과 "AI가 권고를 넘어 실행하려는" 흐름이다. **공공 지침이 줄이라고 하는 쪽**은 바깥에서 OT로 들어오는 연결, 분석·업무 시스템의 직접 제어 권한, OPC DA·평문 Modbus 같은 오래된 프로토콜이다. 두 흐름이 부딪히는 곳(AI 실행 대 직접 제어 금지)이 바로 §5·§6의 쓰기 요청 통로 문제다.

---

## 4. 바깥에서 정한 조치가 설비에 닿는 길 — 외부 시스템별 현업 모범 (설비 ← 외부)

결론 먼저: 현업에서 바깥 시스템은 **"무엇을 할지"를 요청**으로 보낸다. 그 요청은 **OT 쪽이 연 연결로 안에 들어오고**, **경계와 OT 안에서 검증**되며, **받아들일지·언제 할지는 OT 안(L3 운영 시스템·운전원·제어기)이 정한다.** 결과는 응답과 상태로 되돌려 준다. 설비 레지스터에 바로 쓰는 외부 시스템은 공공 지침이 막는다.

### 4-1. 외부 시스템별 — 무엇이 내려오고, 어느 길로, 누가 최종 결정하나

| 외부 시스템 | 올려 보내는 것(요약) | 내려오는 것(무엇을) | 현업 길 | 최종 결정 | 근거 |
|---|---|---|---|---|---|
| **ERP(L4)** | 생산 실적, 자재 소비 | 생산 요청·일정(주문 단위) | ERP ↔ MES 거래(ISA-95 Part 5, B2MML). **설비로 직접 가지 않는다.** MES가 받아 작업 단위로 나눈다. | MES(L3)가 일정·배정. 설비 쪽 결정은 L3 아래 | ISA-95 Part 5는 L3–L4 사이와 L3 안의 거래를 정한다 [표준] https://www.isa.org/getmedia/8ab6de45-43da-488e-9c38-e228355c71c9/ISA-95-00-05-2018_toc.pdf (검색 발췌). B2MML 공통 스키마에 거래 동사 쌍이 있다: `TransGetType`/`TransShowType`, `TransProcessType`/`TransAcknowledgeType`, `TransChangeType`/`TransRespondType`, `TransCancelType`, `TransSyncType`, `TransConfirmType` [재단] https://github.com/MESAInternational/B2MML-BatchML `Schema/B2MML-Common.xsd` (원문 확인) |
| **MES·MOM(L3)** | 작업 실적(Job Response), 상태 | **작업 지시(Job Order)**, 레시피·파라미터 | MES → 배치 실행 시스템·PLC·DCS·수작업 워크플로. 표준 인터페이스: OPC UA for ISA-95 Part 4 Job Control(메서드 호출 + 상태기계), VDMA Machinery Job Management(같은 모델을 바탕으로 함), PackML(명령·상태·관리 태그). | **받는 쪽(설비·제어 시스템)이 받을지와 시작 시점을 정한다.** Store = 저장만, Start = 시작 허락, 실제 시작은 받는 쪽이 자원·우선순위로. 거부 코드 "Unable to accept Job Order"가 있다. | "Job Orders are often sent from Level 3 MES/MOM systems to batch execution systems, automation systems (PLCs and DCSs), or workflow systems for manual operations." / Store: "stores the new job order in local storage, but does not start the job order." / ReturnStatus 비트 4 "The Job Order cannot be accepted" / AllowedToStart 상태에서 "the system may automatically start the job order depending on available resources and priorities" [재단·표준] OPC 10031-4 v2.00(2024-02-02) https://reference.opcfoundation.org/specs/OPC-10031-4/4.1 · https://reference.opcfoundation.org/ISA95JOBCONTROL/v200/docs/6.2.1.3 · https://reference.opcfoundation.org/specs/OPC-10031-4/b-2 · https://reference.opcfoundation.org/ISA95JOBCONTROL/v200/docs/6 (원문 확인) / VDMA 발표: "Bring Job (from MES) to the Machinery Item", "Control the Job (abort, pause, etc.)", ISA-95 Job Control을 "Used as base" [재단] VDMA C. Liehr, OPC Day Finland 2023 https://www.automaatioseura.fi/site/assets/files/3895/03_opc_day_finland_2023_opc_ua_for_machinery_bb_job_management_christopher_liehr.pdf (PDF 본문 추출 확인) / PackML: Command·Status·Admin 태그, Admin은 관리자 권한 사용자만 [재단] OPC 30050 https://reference.opcfoundation.org/specs/OPC-30050/4.2.7.2 (검색 발췌) |
| **정비 시스템(CMMS·EAM)** | 상태·가동시간·알람 → 정비 요청 | **정비 작업지시** | 작업지시는 **사람(정비원)** 에게 간다. 설비에 닿는 것은 사람이 하는 정지·잠금·작업이다. CMMS가 PLC에 쓰는 길을 권하는 표준·지침은 **찾지 못함.** | 사업주 책임 아래 정비원·작업지휘자. 운전 정지와 기동장치 잠금은 법 의무(§6-2) | ISA-95 Part 3 정비 활동 모델(요청 → 배정 → 실행 → 추적) [표준] (13번 F2 확인) / 산업안전보건기준에 관한 규칙 제92조 [법령] (§6-2) |
| **기업 히스토리언·분석·BI** | 공정 이력(사본) | **없음(원칙)** | IT는 DMZ 사본을 읽는다(§1 O1). 결과는 사람에게 보고서·권고로 간다. | 해당 없음 | "ensure that monitoring, analytics, and business systems do not have direct control capabilities over OT assets. These systems should be designed to observe and analyse, not command or alter operations." [표준] OT 연결 원칙 2026 p.25 (원문 확인) |
| **공정 최적화(APC·RTO) — 주로 공정 산업** | 공정값 | **설정값(setpoint)** | 최적화 앱 → 검증 기능 → DCS. NOA 해설에서 "M+O → CPC" 통신선 4번이며 검증 기능이 필요하다. | 검증 기능(사람 확인 ~ 자동 범위 검사)을 통과해야 CPC에 들어간다 | "Communication line 4 represents the data flow from M+O into CPC. There must be a secure path from M+O back to CPC domain. Examples are setpoints from advanced process control applications to be sent to DCS. A "verification of request" functionality is needed that could range from human operator verification to automated checks, e.g. for plausible value ranges etc." [독립] S. Sørenes, LinkedIn 2020-08-27 https://www.linkedin.com/pulse/implementation-namur-open-architecture-noa-era-iot-cloud-s%C3%B8renes (원문 확인, 소속 표기 없음) / NE 178 초록 [표준·업계 권고] (§4-2 ③) |
| **클라우드 IIoT 플랫폼** | 텔레메트리 | 원하는 상태(desired state)·명령 | 벤더 예: 클라우드에 "desired" 값을 적으면 **현장 게이트웨이(연결을 연 쪽)** 가 받아 로컬 OPC UA 서버에 쓴다. | 벤더 예시에는 승인·검증·인터록 설명이 없다(예시 코드) | AWS 예제: Shadow Manager → 로컬 MQTT → 사용자 컴포넌트가 OPC UA에 write. 예제 서버는 "MUST NOT be used in any production environment" [벤더 홍보] https://github.com/aws-solutions-library-samples/guidance-for-full-duplex-open-platform-communication-on-aws README (원문 확인) / Azure OPC UA 커넥터 쓰기: 요청 토픽 → 데이터셋 확인 → 응답 [벤더 홍보] (12번 C4 확인) |
| **AI(원인 분석·에이전트)** | — | 권고(조치 제안) | 권고 → 사람이 기존 변경 관리로 결정 → 기존 제어 경로 | 사람 + 제어 영역 | CISA 외 AI-OT 2025 [표준] (12번 §4-3 확인) |

판단:
- 내려오는 것의 **"무엇"이 시스템마다 다르다.** ERP는 주문, MES는 작업 지시, CMMS는 사람에게 가는 작업지시, 최적화는 설정값, AI는 권고다. 바깥에서 설비 값 자체를 정하는 경우는 공정 최적화의 설정값 정도이고, 그것도 검증 기능을 거친다.
- 우리 수업의 "외부에서 정한 조치가 설비에 적용"은 현업 말로 **"작업 지시·설정값 변경 요청이 OT로 들어와 받아들여지는 것"** 이다. AI 권고는 그 요청을 만드는 여러 출처 중 하나다.

### 4-2. 내려오는 길의 공통 모양 — 요청 → 경계 → OT 안의 수용 → 결과

| 단계 | 현업 모범 | 근거(문장·강도) |
|---|---|---|
| ① 연결 방향 | 바깥이 OT로 연결을 열지 않는다. OT 쪽이 밖으로 연결을 열고, 바깥은 DMZ의 중개자까지만 온다. | "All connections with the OT environment should be initiated as outbound connections from within the OT environment." [표준] OT 연결 원칙 2026 p.11 (원문 확인) / "Access from the higher security zone … is generally to "push" data to the DMZ application … Access for the enterprise user is only to pull from the DMZ application server" / 위험은 방화벽이 "only permits connections initiated by control network devices between the control network and DMZ" 이면 줄어든다 [표준] CISA DiD 2016 §2.4.2 p.19–20 https://www.cisa.gov/sites/default/files/recommended_practices/NCCIC_ICS-CERT_Defense_in_Depth_2016_S508C.pdf (PDF 본문 추출 확인) |
| ② 요청의 형태 | 기계가 검사할 수 있는 단순한 구조. 경계마다 스키마로 "알려진 정상"만 통과. **경계는 IT/OT 사이만이 아니라 SCADA·PLC 앞도 포함.** | "schemas should be applied to these data flows." / "Schemas should be used to inspect and verify protocols and data payloads at key trust boundaries. These boundaries may exist between networks (for example the OT/IT boundary) or between services (for example in front of SCADA control software or a programmable logic controller). Ideally, verification should be schema-based and follow a 'known good' model" [표준] OT 연결 원칙 2026 p.17 (원문 확인) |
| ③ 경계 검증 | 요청을 정해진 처리 순서로 경계를 넘긴다. 요청자는 공장 내부를 몰라도 되고, 처리 상태만 받는다. | NE 178 초록: "information (change requests) to be communicated automatically from the "outside" psM+O back into the OT CPC without adversely impacting availability or safety of the plant" / "a sequence of technology-agnostic information processing steps that need to be applied to requests so they can safely & securely traverse the IT/OT domain boundaries" / "separation of concern between request issuer and plant owner" / "a feedback mechanism that keeps request issuers appraised of their request processing status within VoR while ensuring no plant-specific information is disclosed" [표준·업계 권고] NAMUR 2025-03-10 https://www.namur.net/en/publications/news-archive/ne178-namur-open-architecture-verification-of-request-is-newly-published.html (원문 확인). 본문은 유료라 단계 이름·"최종 권한" 문장은 [미확인] |
| ④ OT 안의 수용 | 받는 쪽이 저장·시작 허락·실제 시작을 나눠 다루고 거부할 수 있다. 제어기는 운전 모드·인터록으로 최종 판단. | OPC UA Job Control(§4-1) [재단·표준] / MTP 운전 모드 Offline/Operator/Automatic (13번 B3 확인) / IEC 104 운영 지침: 긍정 확인 = 인터록 허용 (13번 B2 확인) |
| ⑤ 결과 되돌림 | 명령 응답(받음·거부)과 설비 새 상태를 따로 올린다. | 13번 B2 확인(되읽기 두 겹) / ISA-95 Part 5 거래 쌍 PROCESS↔ACKNOWLEDGE, CHANGE↔RESPOND (§4-1) |
| ⑥ 바깥이 끊겨도 | OT는 혼자 돈다. 바깥 연결만 끊는 격리 계획을 둔다. | "New interdependencies and single points of failure: … could a business system outage cause an OT process to shut down?" / "Manual fallback capability" [표준] p.7 / "OT systems that provide critical functions should, where possible, be designed to facilitate isolation, allowing them to function independently of external dependencies." [표준] p.31 (원문 확인) |
| ⑦ 누가 했나 | 사람별 감사 추적, 최소 권한, 사람-기계 연결은 MFA | "Access to human-to-machine connectivity should require MFA in order to protect sensitive information and prevent unauthorised control actions." / "the connectivity should be user aware so actions produce an employee specific audit trail." [표준] p.21 (원문 확인) |

- 층 사이 역할을 한 문장으로 쓴 글: "Orchestration decides what work to dispatch. Levels 0 to 2 decide whether that work is physically allowed to happen. Commands and state reads cross into level 2. Safety and the real-time control loop stay below the boundary." [벤더 홍보] K. Waehner 블로그 2026-08-28(Kafka 진영 저자, 12번과 같은 이유로 벤더 쪽 표시) https://www.kai-waehner.de/blog/2026/08/28/unified-orchestration-in-manufacturing-from-shop-floor-to-cloud/ (원문 확인). 이 글 하나로 주류라 하지 않는다. 같은 뜻이 OPC UA Job Control(받는 쪽이 시작 결정)과 OT 연결 원칙 p.25(업무·분석 시스템은 직접 제어 능력 없음)에도 있다.

### 4-3. 조치를 메시지 경로(MQTT·Kafka)로 보내도 되나

| 사실 | 근거 |
|---|---|
| 브로커로 명령을 보내는 것 자체는 표준에 있다. Sparkplug NCMD/DCMD(QoS 0, retain 금지). OPC UA PubSub(Part 14 v1.05)에도 요청·응답형 **Actions**(ActionTargets, ActionState)가 정의돼 있다. | [재단] Sparkplug 3.0 (12번 확인) / [재단] https://reference.opcfoundation.org/Core/Part14/v105/docs/6.2.11.2 · https://reference.opcfoundation.org/Core/Part14/v105/docs/6.2.3.10.3 (검색 발췌) |
| NE 178 검증을 "OPC UA PubSub Actions over MQTT"로 구현한 학술 발표가 있다(IEEE). | [독립] https://ieeexplore.ieee.org/document/10275714/ (제목만 검색 발췌, 본문 [미확인]) |
| 브로커 경유 명령은 장치 ACK와 재시도를 따로 만들어야 한다. | [독립·SI] Automation World 2023 (13번 B1 확인) |
| Kafka는 경성 실시간·안전 제어용이 아니다: "An orchestration engine is fast, but it retries and escalates when something runs late. A safety PLC or an AMR traffic controller has no such fallback" | [벤더 홍보] Waehner 2026-08-28 (원문 확인) |
| 공공 지침은 OT와 IT 사이 교환 프로토콜 예로 "OPC UA over TLS, MQTT over TLS, HTTPS"를 든다. Kafka 이름은 없다. | [표준] OT 연결 원칙 2026 p.19 (원문 확인) |
| 양방향을 위해 다이오드를 방향마다 하나씩 두고 소프트웨어로 조율하는 구성은 "anti-pattern"이다. | [표준] p.22 (원문 확인) |

판단:
- **메시지 경로로 조치 요청을 보내는 것은 허용되는 현업 방식이다.** 금지 문장은 찾지 못했다. 조건은 네 가지다: ① OT 쪽이 연결을 연다, ② 요청은 만료·ID·스키마가 있는 "요청"이다(레지스터 값 쓰기가 아님), ③ OT 안에서 다시 검사하고 제어기가 최종 판단한다, ④ 응답·상태를 되돌린다.
- **Kafka는 IT 쪽 요청 장부(기록·감사·재생)로 쓰고 OT 안까지 들이지 않는다.** OT로 들어가는 마지막 구간은 MQTT(또는 OPC UA)다. 운전원 조작은 Kafka·IT가 멈춰도 돼야 한다(§4-2 ⑥).

---

## 5. 누가 결정하나 — 결정이 층마다 나뉜다

| 결정 | 누가 | 어디서 | 근거 |
|---|---|---|---|
| **무엇을 할지**(주문·작업 지시·정비 필요·설정값 제안) | 업무 쪽: 생산 계획(ERP·MES), 정비 계획(CMMS), 최적화·분석, AI 권고 | IT 또는 L3 | ISA-95 Part 3·5 [표준] / OT 연결 원칙 p.25: 분석·업무 시스템은 "observe and analyse" [표준] |
| **그 변경을 허락할지**(변경 관리) | 책임자가 정한 사람(변경 관리 절차). AI 권고도 이 절차로 | 조직 절차 | "Organisations should maintain robust change management processes" [표준] OT 연결 원칙 p.15 (원문 확인) / AI 권고를 "기존 변경 관리 절차"에 넣음 [표준] CISA AI-OT (12번 확인) / 연결마다 "Senior Accountability: who is the senior risk owner" [표준] p.5 (원문 확인) |
| **지금 받아들여 실행할지** | OT 안의 받는 쪽: L3 운영 시스템(작업 지시 수신기), 운전원 확인(선택), 제어기의 운전 모드 | OT | OPC UA Job Control: Store/Start 분리, 시작은 받는 쪽, 거부 가능 [재단·표준] (§4-1) / NE 178: 요청자와 공장 소유자의 관심사 분리 [표준·업계 권고] / 검증은 "human operator verification ~ automated checks" [독립] (§4-1) / MTP Operator·Automatic 출처 구분 (13번 B3) |
| **물리적으로 해도 되는지** | 제어기(인터록·범위), 안전계장(SIS, 독립) | OT L1 | 13번 B4·12번 H1s 확인 / "Levels 0 to 2 decide whether that work is physically allowed to happen." [벤더 홍보] Waehner (§4-2) |
| **사람이 설비에 손댈 때** | 사업주(작업지휘자 배치 등), 정비원 | 현장 | 산업안전보건기준에 관한 규칙 제92조 [법령] (§6-2) |

판단:
- 현업은 **"업무가 무엇을 정하고, 공장(OT)이 할지를 정한다"** 로 나뉜다. IT의 승인은 "변경을 허락"하는 결정이고, "지금 설비가 받아들일지"는 OT 안에서 한 번 더 정한다.
- 우리 설계의 "사람 승인(IT) → … → PLC 최종 판단"은 첫째·넷째 결정은 있지만, **셋째(OT 안의 수용 — 운전원 확인 또는 제어기 모드로 받을지)** 가 드러나 있지 않다. §7에서 고친다.

---

## 6. 적용되는 규칙 — 먼저 "누구에게 적용되나", 다음 "무엇을 요구하나"

강도 표시: **반드시** = 법령 의무(대상이면 지켜야 함) / **표준 shall** = 표준 안의 요구. 표준을 채택·계약·인증할 때 지켜야 함 / **권고** = 공공 지침의 should / **예시** = 지침·벤더가 든 예.

### 6-1. 적용 여부 판정

| 규칙 | 누구에게 적용되나 | 일반 제조 공장(우리 가정: 국내 기계·유압 설비 공장)에 적용? | 근거 |
|---|---|---|---|
| **산업안전보건기준에 관한 규칙** 제92조(정비 시 운전정지)·제224조(로봇 수리 시 조치) | 사업주 | **적용.** 동력 기계를 쓰는 모든 사업장 | [법령] 국가법령정보센터 Open API, 고용노동부령, 시행 2025-09-01 https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&ID=007363&type=XML (원문 확인) |
| **산업안전보건법** 제44조 공정안전보고서(PSM) | "대통령령으로 정하는 유해하거나 위험한 설비"가 있는 사업장 | **해당 설비가 있을 때만.** 유압 기계 공장은 보통 아님(판단) | [법령] 산업안전보건법 제44조 (원문 확인, 법령ID 001766) |
| **정보통신기반 보호법** | 중앙행정기관의 장이 **지정한** 주요정보통신기반시설의 관리기관 | **지정된 곳만.** 일반 공장은 지정 대상이 아니면 해당 없음 | 제8조 ① "중앙행정기관의 장은 … 주요정보통신기반시설로 지정할 수 있다" [법령] 시행 2025-01-24 (원문 확인, 법령ID 009182) |
| **중소기업 스마트제조혁신 촉진에 관한 법률** 제18조(보안 강화) | 중소벤처기업부장관(지원 사업) | **공장에 주는 의무 없음.** 정부가 "보안시스템 구축, 보안 진단 및 자문, 기술보호관제서비스"를 추진"할 수 있다" | [법령] 시행 2023-07-04 (원문 확인, 법령ID 014379) |
| **산업기술보호법** 제11조 | 국가핵심기술 보유 기관의 수출 | 설비 연결 구조와 **직접 관계 없음**(판단) | [법령] (원문 확인, 법령ID 010306) |
| **IEC 62443 / KS X IEC 62443** | 채택·계약·인증하는 자산 소유자·통합자·공급자 | **자발적 표준.** 고객·계약이 요구하면 적용. 국내 KS 부합화판 있음(4-2부 2020 제정 등) | [표준] KSSN https://www.kssn.net/search/stddetail.do?itemNo=K001010153532 (검색 발췌) / 3-3부 KS 제목 (검색 발췌, KIISC 2020) |
| **ISA-95 / IEC 62264, OPC UA 컴패니언(ISA-95 Job Control, Machinery, PackML)** | 통합 설계자 | **자발적.** 현업 통합의 공통 언어 | [표준]·[재단] (§4-1) |
| **OT 연결 원칙 2026(NCSC·CISA·FBI·BSI 등 8개 기관)** | 모든 OT 시스템 소유자(특히 필수 서비스 운영자) | **권고.** 문서 스스로 "desirable end-states … intended as goals rather than minimum requirements" | [표준] p.4 (원문 확인) |
| **CISA 외 AI-OT 원칙 2025, CISA DiD 2016, NIST SP 800-82r3** | OT 소유자(미국 지침이나 국제적으로 참조) | **권고** | [표준] (12번 확인) |
| **KISA 스마트공장 보안모델 Part Ⅱ: 대외 연계구간(2021-12, 요약본)** | 스마트공장 보안 담당자 | **권고(참고용).** 문서 목적: 보안 담당자가 "참고하고 활용할 수 있도록" | [표준·공공 지침] https://www.kisa.or.kr/post/fileDownload?menuSeq=2060205&postSeq=11&attachSeq=2&lang_type=KO (PDF 본문 추출 확인) |
| **KISA OT 환경 제로트러스트 적용 안내서(2025-12-22)** | OT 운영 조직 | **권고.** 원칙: 실시간성·가용성 유지, OT 장비 독립성 유지, OT·IT 전역 침해 가정, 지속적 모니터링. Purdue 모델 포괄 | [표준·공공 지침] KISA 보도자료 https://www.kisa.or.kr/402/form?postSeq=2566 (원문 확인). 안내서 본문은 읽지 못함 [미확인] |
| **EU 기계 규정 2023/1230** 부속서 III 1.1.9(부패 방지)·1.2.1 | EU에 기계를 내놓는 제조사 | 공장 통합자에는 **해당 없음.** 기계를 EU에 수출할 때만. 적용일 2027-01-20 | [법령] (검색 발췌) https://www.nemko.com/blog/eu-machinery-regulation-2023/1230 |
| **21 CFR Part 11** | FDA 규제 대상(제약·식품 등) | **해당 없음**(13번 D2 확인) | [법령] |

판단: 우리 시스템(국내 일반 제조 공장을 흉내 낸 교육용)에 **법으로 "반드시"인 것은 산업안전 규칙(정비 시 정지·잠금)뿐**이다. OT–외부 연결 구조 자체를 정하는 국내 법 조문은 일반 공장에는 **찾지 못했다**(정보통신기반 보호법은 지정 시설만). 나머지는 표준(자발)과 공공 지침(권고)이다. 그래서 "지켜야 할 것"은 **①법 의무 + ②여러 공공 지침이 같은 말을 하는 곳(= 업계 공통 관행)** 으로 정하는 것이 맞다(의뢰서 §9 기준).

### 6-2. 요구 문장과 강도

| # | 요구(쉬운 말) | 원문 | 강도 | 출처 |
|---|---|---|---|---|
| R1 | 정비·수리·조정 때 위험하면 기계를 멈춘다 | "사업주는 동력으로 작동되는 기계의 정비ㆍ청소ㆍ급유ㆍ검사ㆍ수리ㆍ교체 또는 조정 작업 … 을 할 때에 근로자가 위험해질 우려가 있으면 해당 기계의 운전을 정지하여야 한다." | **반드시** | 산업안전보건기준에 관한 규칙 제92조① [법령] (원문 확인) |
| R2 | 멈춘 기계를 남이 켜지 못하게 잠그거나 표지를 단다 | "다른 사람이 그 기계를 운전하는 것을 방지하기 위하여 기계의 기동장치에 잠금장치를 하고 그 열쇠를 별도 관리하거나 표지판을 설치하는 등 필요한 방호 조치를 하여야 한다." | **반드시** | 같은 조② [법령] (원문 확인) |
| R3 | 갑자기 가동될 우려가 있으면 작업지휘자 배치 등 | "기계가 갑자기 가동될 우려가 있는 경우 작업지휘자를 배치하는 등 필요한 조치를 하여야 한다." | **반드시** | 같은 조③ [법령] (원문 확인) |
| R4 | 로봇 수리 등 작업 시 운전 정지, 기동스위치를 다른 사람이 조작 못 하게 | 제224조: "… 해당 작업에 종사하고 있는 근로자가 아닌 사람이 해당 기동스위치를 조작할 수 없도록 필요한 조치를 하여야 한다." | **반드시**(로봇이 있을 때) | [법령] (원문 확인) |
| R5 | OT와의 연결은 OT 안에서 밖으로 연다. 바깥이 들어와야 하면 DMZ 중개 | p.11 "should be initiated as outbound connections from within the OT environment" | 권고(여러 지침 공통) | OT 연결 원칙 2026 [표준] / CISA DiD 2016 [표준] |
| R6 | 운영 데이터 공유는 OT 히스토리언 → DMZ 히스토리언 단방향 복제, IT는 DMZ를 HTTP API로 조회 | p.19 "replicate the OT historian to a historian instance in the DMZ via a unidirectional, secure transfer mechanism … IT systems should query the DMZ historian via a secure HTTP-based API" | 권고 + **예시**(구체 방법) | [표준] (원문 확인) |
| R7 | 분석·업무 시스템은 OT를 직접 제어하지 못한다 | p.25 "do not have direct control capabilities over OT assets … observe and analyse, not command or alter operations" | 권고 | [표준] (원문 확인) |
| R8 | 경계(IT/OT, SCADA·PLC 앞)에서 스키마로 알려진 정상만 통과 | p.17 (§4-2 ②) | 권고 | [표준] (원문 확인) |
| R9 | 바깥 쓰기 요청은 검증 기능을 거쳐 CPC로, 요청자는 상태만 받음 | NE 178 초록 (§4-2 ③) | 업계 권고(공정 산업 사용자 단체) | [표준·업계 권고] |
| R10 | 연결마다 문서화된 사업 근거·위험 책임자 | p.5 "The first step for all OT connectivity should be the documentation of a formal business case" | 권고 | [표준] (원문 확인) |
| R11 | 사람-기계 연결은 MFA, 사람별 감사 추적, 최소 권한 | p.21 (§4-2 ⑦) | 권고 | [표준] (원문 확인) |
| R12 | 바깥이 끊겨도 OT가 돌고, 격리 계획을 시험한다 | p.7, p.31 (§4-2 ⑥) | 권고 | [표준] (원문 확인) |
| R13 | 산업 제어 프로토콜(Modbus 등)은 격리된 OT 구획 안에만 | p.19 "Industrial control protocols (Modbus, OPC DA, EtherNet/IP, etc.) should be restricted to isolated OT network segments." | 권고 | [표준] (원문 확인) |
| R14 | 모든 연결을 기록·감시. 유지보수 중 끈 감시 규칙은 창이 끝나면 다시 켠다 | p.29 | 권고 | [표준] (원문 확인) |
| R15 | 구역 경계 보호, 기본 거부(deny by default), 입력 검증, 결정적 출력, 감사 대상 사건·부인 방지 | SR 5.1 망 구획, SR 5.2 구역 경계 보호, SR 3.5 입력 검증, SR 3.6 결정적 출력, SR 2.8 감사 대상 사건, SR 2.12 부인 방지. SR 5.2 RE1 "deny by default, allow by exception"은 SL2부터 | **표준 shall**(채택 시). SR 이름은 목차 원문 확인, RE 내용은 해설 | [표준] IEC 62443-3-3:2013 미리보기 목차 (원문 확인, 13번과 같은 파일) / RE 내용 (검색 발췌, 벤더 해설 https://info.cyolo.io/hubfs/7608544/At-A-Glances/AAG_%20ISA%20IEC%2062443%20compliance.pdf) |
| R16 | 외부 연계 MES·엣지 컴퓨터는 공장망에서 **Industrial DMZ로 분리**, 공장망 접근 차단, "공장망 분리, 일방향 네트워크 구성" | "MES를 공장망에서 Industrial DMZ로 분리하고, 공장망 접근차단 정책 적용" / "엣지컴퓨터를 공장망에서 Industrial DMZ로 분리하고, 공장망 접근차단 정책 적용" (보안기술 칸: "공장망 분리, 일방향 네트워크 구성") | 권고(국내) | KISA 스마트공장 보안모델 Part Ⅱ 요약본 PDF 10쪽(MES)·16쪽(엣지) [표준·공공 지침] (PDF 본문 추출 확인) |
| R17 | 원격 유지보수: 지정 IP만 접근, 통신 암호화, well-known 포트 원격접속 차단, 이상 징후 탐지 | 원격유지보수 구간 요구사항 | 권고(국내) | 같은 문서 PDF 15쪽 (PDF 본문 추출 확인) |
| R18 | 명령 메시지는 남겨 두지 않는다(retain 금지) | Sparkplug NCMD/DCMD | 표준 shall(Sparkplug 채택 시) | [재단] (12번 확인) |

판단:
- **"반드시"(법)** 는 R1~R4뿐이며, 모두 **정비 조치가 사람을 통해 설비에 닿을 때**의 규칙이다. 즉 CMMS 작업지시를 수업에 넣으면 "정지·잠금 확인"이 빠지면 안 된다.
- 연결 구조의 핵심(R5·R7·R8·R12)은 **여러 나라 공공 지침이 같은 말**을 한다(OT 연결 원칙 2026은 8개 기관 공동, CISA DiD 2016, NIST 800-82r3, 국내 KISA 보안모델도 DMZ 분리·일방향). 현업 공통 관행으로 보고 지킨다.
- KISA 모델은 **외부와 이어지는 MES를 Industrial DMZ에 둔다.** Purdue 기본형은 MES를 L3(OT 안)에 둔다(12번 확인). 두 배치가 공존한다. 공통점은 "외부와 직접 닿는 것은 DMZ, 공장망 안으로는 차단"이다.

---

## 7. 우리 설계가 어긋나는 곳과 고칠 것

지금 설계(의뢰서 §9): 데이터 = 허브 → DMZ 중계 → Kafka / 조치 = 사람 승인 → Kafka → DMZ 게이트웨이 → 허브 → 엣지 → PLC. 스택은 14번(Mosquitto 2.1.2, Bento 1.21.2, Kafka 4.3.1, InfluxDB 2.9.1, FUXA 1.3.4, Node-RED 5.0.7, OpenPLC v4)을 전제로 한다.

| # | 항목 | 지금 설계 | 현업 모범·규칙 | 고칠 것 | 강도·이유 |
|---|---|---|---|---|---|
| G1 | **올라가는 연결을 누가 여나** | DMZ 중계(Bento)가 OT 허브를 구독하면 **DMZ가 OT로 연결을 연다** | OT가 밖으로 연다(R5). 경로는 DMZ에서 끝난다(CISA DiD) | OT 허브(Mosquitto)의 **브리지 `out`** 이 DMZ 브로커로 밀어낸다. DMZ 안의 것은 OT로 연결을 열지 않는다 | 권고(여러 지침 공통). Mosquitto 브리지는 로컬 브로커가 원격으로 연결을 열고 방향 `out`/`in`/`both`를 정한다(13번 G1 확인) |
| G2 | **내려가는 연결을 누가 여나** | DMZ 게이트웨이가 OT 허브에 발행 = **바깥에서 OT로 들어오는 연결** | 같음(R5). 벤더 클라우드 예도 현장 게이트웨이가 연결을 열고 요청을 받아 간다(§4-1) | 게이트웨이는 **DMZ 브로커의 요청 토픽**에만 낸다. OT 허브 브리지가 **`in` 방향**으로 그 토픽을 가져온다(연결은 OT가 엶). 끊겼다 이어질 때 요청이 사라지지 않게 브리지는 QoS 1·세션 유지, 대신 **만료 시각으로 늦은 요청을 버린다** | 권고. 만료 검사는 13번 B2(원격제어 운영 지침의 시각 검사)와 같다. Mosquitto: `in` = "import messages from a remote broker", 토픽마다 QoS 지정, `cleansession` 기본 false = "all subscriptions on the remote broker are kept in case of the network connection dropping" [재단] https://mosquitto.org/man/mosquitto-conf-5.html (원문 확인) |
| G3 | **내려오는 것의 모양** | "명령"(정지 등 설비 쓰기) | ERP·MES·CMMS·최적화는 **요청**을 보내고, 받는 쪽이 받거나 거부한다(§4-1, ISA-95 거래 쌍, Job Control 상태) | 메시지를 **"작업 요청"** 으로 바꾼다: 요청 ID, 출처 종류(MES·CMMS·최적화·AI·운전원), 대상 자산 ID, **허용 목록 안의 동작 이름**, 파라미터, 만료 시각, 요청자·승인자 ID. 응답은 두 겹: ① 수용/거부 + 이유 코드(ISA-95 ACKNOWLEDGE, Job Control ReturnStatus 흉내) ② 실행 결과·설비 새 상태 | 권고(R8·R9). 레지스터 주소가 IT에 드러나지 않게 한다(NE 178 "요청자는 공장 내부를 몰라도 됨") |
| G4 | **검증을 어디서 하나** | DMZ 게이트웨이 한 곳 + PLC | 경계마다 스키마(IT/OT 경계 **그리고** SCADA·PLC 앞)(R8). 제어기가 최종(§5) | 세 겹: ① DMZ 게이트웨이: 스키마·허용 목록·만료·중복·요청자 권한 ② **OT 수신기**: 스키마 재검사·운전 모드 확인·필요하면 운전원 확인 ③ PLC: 모드·범위·인터록·중복 | 권고. 한 곳이 뚫려도 다음 겹이 막는다(심층 방어) |
| G5 | **OT 안에서 받을지를 누가 정하나** | 드러나지 않음(IT 승인이 곧 실행) | 업무는 무엇을, 공장은 할지를 정한다(§5). 검증은 "human operator verification ~ automated checks" | OT 수신기 규칙: 제어기가 **자동 수용 모드(REMOTE_AUTO)** 일 때만 자동 수용. 아니면 **FUXA 화면에 "받은 요청"으로 띄우고 운전원이 수락/거부.** 수동 조작이 들어오면 자동 수용을 끈다(참조 v3 모드 규칙과 같음) | 권고. MTP의 Operator/Automatic 출처 구분(13번 B3)으로 표준 근거가 붙는다 |
| G6 | **L3 운영 층(OT 안의 수신기)** | 없음. 게이트웨이가 곧바로 허브·엣지로 | MES(L3)가 작업 지시를 받아 설비 단위로 나누고 결과를 모은다(§4-1). KISA 모델은 외부와 닿는 MES를 Industrial DMZ에 둔다 | OT 안에 **"작업 요청 수신기"(MES-lite)** 를 둔다. 새 컨테이너 대신 **Node-RED(B2)의 흐름 하나**로 시작(판단). 동작 이름 → 제어기 명령 토픽으로 바꾸는 표는 설비 등록부(B11)에서 만든다 | 판단(현업 층을 빼지 않기 위해). 제품은 교육용 흉내 |
| G7 | **Kafka를 조치 길에 쓰는 것** | 승인 → Kafka → 게이트웨이 | 금지 문장 없음. Kafka는 경성 실시간·안전용이 아님. 지침의 경계 프로토콜 예는 MQTT·OPC UA·HTTPS(§4-3) | **유지하되 역할을 "IT 쪽 요청 장부·감사"로 한정.** OT 안에는 Kafka 없음. DMZ를 넘는 구간은 MQTT(또는 HTTPS API) | 판단 + 권고(R13: 제어 프로토콜은 OT 안에만) |
| G8 | **DMZ가 IT 쪽으로 연결을 여나** | Bento(DMZ) → Kafka(IT) 쓰기, 게이트웨이(DMZ) ← Kafka(IT) 읽기 = DMZ가 IT로 연결을 엶 | "By placing corporate-accessible components in a DMZ, no direct communication paths are required … each path effectively ends in the DMZ" / 기업 사용자는 DMZ에서 **가져간다(pull)** (CISA DiD §2.4.2) | 가능하면 **양쪽이 DMZ로 들어오게** 한다: 상향은 IT 쪽 수집기(Bento를 it-net에 두고 DMZ 브로커 구독 → Kafka), 하향은 IT 쪽 발송기가 DMZ 게이트웨이 API(또는 DMZ 브로커)에 넣는다 | **판단(약함).** OT 쪽 방향(G1·G2)만큼 강한 문장은 없다. 메모리 차이 없음 → 선택 |
| G9 | **공장 안 히스토리언과 DMZ 사본을 둬야 하나** | OT 이력 없음(HMI 현재값만). 이력 정본은 IT InfluxDB | R6: OT 히스토리언 → DMZ 히스토리언 단방향 복제, IT는 DMZ를 HTTP API로(권고 + 예시). 13번 D1: "OT에 꼭 둬야 한다"는 요구 문장은 없음 | ① **OT 짧은 이력: FUXA DAQ(SQLite)를 켠다** — 새 컨테이너 없음. FUXA 소스에 저장 백엔드 `sqlite`·`influxdb`·`tdengine`·`questdb`가 있다 [재단] https://github.com/frangoteam/FUXA `server/runtime/storage` (GitHub API 목록 원문 확인). ② **원시 태그 InfluxDB를 DMZ로 옮기는 안**(선택): DMZ 브로커 → (DMZ 안) → InfluxDB, Grafana·AI는 HTTP API로 조회 → R6와 같은 모양. 옮기지 않으면 "IT의 기업 히스토리언(사본)"이라고 설명 | ①은 권고(R12: 바깥이 끊겨도 OT에서 추세를 봄). ②는 R6 예시를 그대로 따르는 선택. 메모리는 배치만 바뀌어 차이 없음(판단, 실측 안 함) |
| G10 | **외부 시스템 종류** | AI(원인 분석·승인)만 | ERP·MES·CMMS·최적화·클라우드·AI 전부(§4-1) | 요청 출처를 셋 이상 둔다: ① 생산 작업 지시(MES·ERP 흉내: 시작·정지·파라미터) ② 설정값 변경 요청(최적화 흉내) ③ 정비 작업지시(CMMS 흉내 → 사람 경로, G11) ④ AI 권고 → 사람이 ①~③ 중 하나로 바꿔 승인 | 의뢰서 §9 요구. AI를 기준에서 뺀다 |
| G11 | **정비 조치가 설비에 닿는 길** | 없음 | 사람이 정지·잠금(R1~R3 **반드시**) | soft-PLC에 **"정비 잠금" 상태**를 둔다: 켜져 있으면 모든 원격 요청 거부, HMI에 잠금·담당자 표시, 잠금 해제는 현장(LOCAL)에서만. CMMS 작업지시는 "잠금 확인됨"이 기록돼야 완료 | 법 의무(R2)의 교육용 흉내(판단). 실제 법 의무는 물리 잠금장치·열쇠 관리다 |
| G12 | **감사와 신원** | 승인·실행 기록(부분) | 사람별 감사 추적(R11), 감사 대상 사건·부인 방지(R15), AI 신원 구분(CISA AI-OT, 12번) | 요청·승인·경계 검사·OT 수용/거부·실행 결과를 **같은 요청 ID로** 추가만 되는 기록에 남긴다. 주체 칸에 사람 ID / 시스템 ID / AI ID를 나눈다 | 권고 |
| G13 | **격리 계획** | 없음 | 격리 계획을 만들고 시험한다(R12, OT 연결 원칙 원칙 8) | 실습 하나: DMZ 브로커를 멈추거나 브리지를 끊는다 → FUXA 감시·수동 조작·인터록·FUXA DAQ 이력이 계속 되는지 확인 → 다시 이을 때 만료된 요청이 버려지는지 확인 | 권고 |
| G14 | **연결 목록(사업 근거)** | 없음 | 연결마다 필요·이익·위험·책임자 문서화(R10) | 문서 한 장: 연결마다 "누가 열고, 무엇이, 어느 방향, 왜, 끊기면 어떻게" | 권고. 학생이 구조를 설명하는 도구로도 쓴다 |
| — | (이미 결정) AI의 Modbus 직접 쓰기·FUXA 직접 쓰기 제거, 명령 retain 금지, 제어기 ACK | 12번·13번에서 결정 | R7·R18 | 유지 | — |

바뀐 길(판단, 위 G1~G9 반영):
- **데이터 ↑:** 설비 → PLC → 엣지 → OT 허브 →(브리지 `out`, OT가 엶)→ DMZ 브로커 → {DMZ 히스토리언(선택), IT 수집기 → Kafka → Flink·InfluxDB·AI}. OT 안에서는 FUXA가 허브 구독 + DAQ 이력.
- **조치 ↓:** 요청 출처(MES·CMMS·최적화·AI 권고) → IT 승인(변경 관리) → Kafka(요청 장부) → IT 발송기 → DMZ 게이트웨이(1차 검사) → DMZ 브로커 요청 토픽 →(브리지 `in`, OT가 엶)→ OT 허브 → **OT 수신기(2차 검사, 모드·운전원 확인)** → 제어기 명령 토픽 → PLC(최종: 모드·범위·인터록·중복·정비 잠금) → 설비.
- **결과 ↑:** PLC 응답(수용/거부+이유) + 새 상태 → OT 허브 →(브리지 `out`)→ DMZ 브로커 → IT → Kafka → 승인 흐름이 요청 ID로 대조 → 재관측 → 기록.
- **운전원 ↓:** FUXA → OT 허브 → 제어기. IT·DMZ와 무관.

---

## 8. 학생 PC에서 무료로 흉내 내기 — 방법과 한계

조건: PC 한 대, 도커 약 7.6 GB, 비용 0, 금지 라이선스·상용 전용 기능 제외(의뢰서 §1). 아래 "추가 메모리"는 14번 실측값을 빌린 추정이며 이번에 새로 잰 것은 없다.

| 현업 요소 | 무료 흉내 | 라이선스·판(확인한 것) | 추가 비용 | 한계(학생에게 말할 것) |
|---|---|---|---|---|
| OT / DMZ / IT 구역 | 도커 bridge 망. 두 망에 붙는 것은 DMZ 컨테이너뿐(12번 권장, 13번 G1). 방향을 **강제**까지 하려면 GRFICSv3처럼 라우터 컨테이너 하나를 두고 규칙을 건다(선택) | Docker 문서: 다른 bridge 망끼리는 공개 포트로만 통신 (13번 G1 확인) | 없음(라우터는 선택) | bridge 망만으로는 "누가 연결을 여나"를 **설정으로만** 지킨다. 라우터 규칙은 Windows Docker Desktop에서 실행 확인 안 함 [미확인] |
| DMZ 만남 장소(브로커) | **두 번째 Mosquitto**를 DMZ에 둔다. OT 허브 브리지가 `out`(데이터·응답)·`in`(요청)으로 이 브로커에 연결을 연다 | Mosquitto 2.1.2(14번). 브리지 방향·세션 옵션 (§7 G2 원문 확인) | 약 5 MiB(14번 실측 기준 추정) | 하드웨어 단방향이 아니다 |
| OT 짧은 이력(사이트 히스토리언) | FUXA DAQ 저장(SQLite) 켜기 | FUXA 1.3.4, 저장 백엔드 sqlite 등 (§7 G9) | 새 컨테이너 없음 | 현업 사이트 히스토리언보다 기능이 작다(압축·복제 없음) |
| DMZ 사본 히스토리언 + HTTP API | (선택) 원시 태그 InfluxDB를 DMZ에 두고 Grafana·AI가 HTTP API로 조회 | InfluxDB 2.9.1(14번) | 배치만 바뀜 | 복제가 "단방향 전송 장치"가 아니라 브로커 구독이다 |
| MES(L3) 작업 지시 수신 | OT 안 **Node-RED 흐름**: 요청 스키마 재검사 → 운전 모드 확인 → 필요하면 FUXA에 "받은 요청" 표시 → 제어기 명령 토픽 | Node-RED 5.0.7 Apache-2.0(14번) | 새 컨테이너 없음(B2 재사용, 판단) | 상용 MES의 일정·자원 관리 없음 |
| (심화) 표준 작업 지시 인터페이스 | Python `asyncua` 서버에 **OPC UA ISA-95 Job Control 노드셋**을 올려 Store/Start/Abort와 상태기계를 흉내 | asyncua LGPL-3.0, 2026-09-16 push [재단] https://github.com/FreeOpcUa/opcua-asyncio / 노드셋 `opc.ua.isa95-jobcontrol.nodeset2.xml` Version 2.0.0(2024-01-31), "OPC Foundation MIT License 1.00" [재단] https://github.com/OPCFoundation/UA-Nodeset `ISA95-JOBCONTROL/` (원문 확인) | 컨테이너 1개(메모리 미측정) | 노드셋 불러오기·메서드 구현은 **실행 확인 안 함** [미확인]. 의존 노드셋(ISA-95 기본 등) 필요 여부도 [미확인] |
| ERP·MES·CMMS·최적화 요청 출처 | **작은 "업무 시스템 흉내" 앱 하나**(IT): 생산 작업 지시 / 설정값 변경 요청 / 정비 작업지시 세 화면. 표는 기존 PostgreSQL(X3). 메시지 필드는 **B2MML(JSON판 포함) 이름**을 빌린다 | B2MML: 무료 사용·수정·재배포 허용, 조건은 MESA를 원작자로 밝히는 문장 [재단] https://github.com/MESAInternational/B2MML-BatchML `LICENSE` (원문 확인). 저장소에 `Schema/AllSchemas.json` 있음 (원문 확인) | 자체 코드(작음) | 실제 ERP·CMMS의 업무 규칙은 없다 |
| (선택) 실제 오픈소스 ERP·정비 | **Odoo 20.0 Community**: 제조(`mrp`)·정비(`maintenance`) 모듈이 커뮤니티 저장소에 있다. 공식 이미지 태그 `odoo:20.0-20260926` | LGPL-3.0(저장소 LICENSE, 원문 확인) / `addons/mrp`·`addons/maintenance`의 `__manifest__.py` 20.0 브랜치 존재, `mrp_workorder`·`quality`는 커뮤니티 저장소에 없음(GitHub API 404, 원문 확인) / Docker Hub 태그 (원문 확인) | 메모리 **미측정** | 작업장 태블릿 기능(`mrp_workorder`)은 커뮤니티에 없음 → 그 기능은 쓰지 않는다(관문: 상용 전용 기능 금지) |
| (비추천) Atlas CMMS | — | AGPL-3.0 또는 상용 이중 라이선스, 상용판에 "Enterprise Features"(가격표 기준) 있음, compose가 postgres·api·frontend·minio·nginx 5개 [재단] https://github.com/Grashjs/cmms `COMMERCIAL_LICENSE.MD`·`docker-compose.yml` (원문 확인) | 5개 컨테이너 | 관문(상용 전용 기능) 확인 부담 + 메모리 → 쓰지 않는다(판단) |
| 변경 관리·승인 | 기존 자체 승인 흐름(B13) | 14번 | 없음 | — |
| 정비 잠금(LOTO) | soft-PLC "정비 잠금" 상태 + HMI 표시 + LOCAL에서만 해제 (§7 G11) | OpenPLC v4(14번) | 없음 | 실제 법 의무는 **물리 잠금장치·열쇠 관리**다. 화면 표시는 대신할 수 없다 |
| 격리 시험 | DMZ 브로커 멈추기·브리지 끊기 실습 (§7 G13) | — | 없음 | — |
| 클라우드 플랫폼 | 흉내 내지 않는다. "현장 게이트웨이가 연결을 열고 desired 상태를 가져와 쓴다"는 벤더 모양만 설명(§4-1) | — | 없음 | 인터넷·계정 필요 → 비용 0 관문과 충돌 가능 |
| 보안 기능(TLS·MFA·L7 방화벽·IDS) | 생략하고 "현업은 켠다"고 설명. 브로커 계정·ACL은 켠다(13번 G2) | — | — | 교육용 축소. 실제 공장에서는 R11·R15에 해당 |

판단:
- **새로 드는 것은 DMZ Mosquitto 하나와 작은 업무 흉내 앱 하나**다. 나머지(OT 수신기, OT 이력, 정비 잠금, 격리 시험)는 이미 있는 Node-RED·FUXA·OpenPLC 설정으로 된다. Odoo와 Job Control 서버는 메모리를 재본 뒤에 넣을지 정한다.
- 줄여도 되는 것: 하드웨어 다이오드, L7 방화벽, TLS·MFA, 실제 ERP·CMMS 제품. **줄이면 현업과 달라지는 것:** 연결 방향(OT가 엶), 요청/응답 모양, OT 안의 수용 결정, 세 겹 검증, 바깥이 끊겨도 OT가 도는 것, 정비 잠금. 이 여섯은 흉내라도 남긴다.

---

## 9. 결론 표

### 9-1. 현업 모범 구조 (외부 ↔ IoT-SCADA 양방향)

| 방향 | 현업 모범 | 근거 강도 |
|---|---|---|
| 밖으로(설비 → 외부) | OT가 밀어낸다. 바깥은 DMZ의 사본(히스토리언 복제)·중개자를 읽는다. IT는 OT에 직접 붙지 않는다 (§1~3) | 권고, 여러 공공 지침 공통 |
| 안으로(외부 → 설비): 무엇이 오나 | 외부 시스템마다 다르다: ERP = 주문, MES = 작업 지시, CMMS = 사람에게 가는 정비 작업지시, 최적화 = 설정값, AI = 권고. **분석·업무 시스템은 직접 제어하지 않는다** (§4-1) | 권고(OT 연결 원칙 p.25) + 표준 인터페이스(ISA-95, OPC UA Job Control) |
| 안으로: 어떻게 오나 | **요청**이 DMZ까지 오고, **OT 쪽이 연 연결**로 가져간다. 경계와 SCADA·PLC 앞에서 스키마 검사. 결과는 수용/거부 응답 + 새 상태 (§4-2) | 권고 + 업계 권고(NE 178) |
| 안으로: 누가 정하나 | 업무가 **무엇을**, 변경 관리가 **허락을**, OT(수신기·운전원·제어기 모드)가 **지금 받을지를**, 제어기·SIS가 **물리적으로 되는지를** 정한다 (§5) | 표준 모델(Job Control) + 권고 |
| 사람이 하는 조치 | 정비 작업지시는 사람이 수행. 정지·잠금·표지는 법 의무 (§6-2 R1~R3) | **법(반드시)** |
| 끊겼을 때 | OT는 혼자 돈다. 바깥 연결만 끊는 격리 계획을 시험한다 | 권고 |
| 메시지 경로 | MQTT·OPC UA로 요청을 보내는 것은 허용. Kafka는 IT 쪽 장부로. 경성 실시간·안전은 제어기 | 금지 문장 없음 + 권고(프로토콜 예) |

### 9-2. 적용 규칙과 요구

| 규칙 | 우리에게 적용? | 무엇을 요구(요지) | 강도 |
|---|---|---|---|
| 산업안전보건기준에 관한 규칙 제92조·제224조 | 적용(동력 기계·로봇 사업장) | 정비 시 운전 정지, 기동장치 잠금·열쇠 관리·표지, 작업지휘자, 압력 방출 / 로봇 기동스위치 조작 방지 | **반드시** |
| 산업안전보건법 제44조(PSM) | 대상 유해·위험 설비가 있을 때만 | 공정안전보고서 | 대상이면 반드시 |
| 정보통신기반 보호법 | 지정된 시설만 | (지정 시) 취약점 분석 등 | 대상 아님(일반 공장) |
| 스마트제조혁신법 제18조 | 공장 의무 없음 | 정부의 보안 지원 사업 근거 | — |
| OT 연결 원칙 2026(8개 기관) | 모든 OT 소유자 | OT가 밖으로 연결(R5), DMZ 히스토리언 복제·HTTP API(R6), 분석·업무 시스템 직접 제어 금지(R7), 경계 스키마 검사(R8), 연결별 사업 근거(R10), MFA·사람별 감사(R11), 격리 계획(R12), 제어 프로토콜은 OT 안(R13), 연결 기록·감시(R14) | 권고("goals rather than minimum requirements") |
| CISA DiD 2016, NIST SP 800-82r3, CISA AI-OT 2025 | 참조 | 3구역 이상, OT가 연 연결만 허용, 기업은 DMZ에서 가져감, AI는 권고·사람 결정 | 권고 |
| KISA 스마트공장 보안모델 Part Ⅱ(2021) | 국내 참고 | 외부 연계 MES·엣지는 Industrial DMZ로, 공장망 접근 차단, 일방향 구성, 원격 유지보수 IP 제한·암호화 | 권고(참고용) |
| KISA OT 제로트러스트 안내서(2025) | 국내 참고 | 가용성 유지, OT 장비 독립성, 침해 가정, 지속 감시 | 권고 |
| IEC 62443-3-3(KS X IEC 62443) | 자발(채택·계약 시) | SR 5.1 구획, SR 5.2 경계 보호(기본 거부), SR 3.5 입력 검증, SR 3.6 결정적 출력, SR 2.8 감사, SR 2.12 부인 방지 | 표준 shall |
| NAMUR NE 178 | 공정 산업 업계 권고 | 바깥 쓰기 요청은 검증 순서를 거쳐 CPC로, 요청자는 상태만 | 업계 권고 |
| ISA-95 Part 5 / OPC UA ISA-95 Job Control / Sparkplug | 자발 | 요청·응답 거래 쌍, 받는 쪽이 저장·시작·거부, 명령 retain 금지 | 표준 shall(채택 시) |
| EU 기계 규정, 21 CFR 11 | 해당 없음 | — | — |

### 9-3. 우리 설계에서 고칠 곳

| 우선 | 고칠 곳 | 이유(규칙) |
|---|---|---|
| 1 | **연결 방향:** DMZ 브로커를 두고 OT 허브 브리지가 `out`(데이터·응답)·`in`(요청)으로 **OT가 연결을 연다.** DMZ 게이트웨이·중계는 OT로 연결을 열지 않는다 (G1·G2) | R5(여러 지침 공통) |
| 2 | **요청 모양:** "명령" → "작업 요청"(ID·출처·대상 자산·허용 동작·파라미터·만료·요청자/승인자) + 두 겹 응답(수용/거부+이유, 실행 결과) (G3) | R8·R9, ISA-95·Job Control |
| 3 | **OT 안의 수용 결정:** OT 수신기(Node-RED)가 모드 확인, 자동 수용 모드가 아니면 FUXA에서 운전원 수락 (G5·G6) | §5, NE 178, MTP |
| 4 | **세 겹 검증:** DMZ 게이트웨이 + OT 수신기 + PLC (G4) | R8(PLC 앞 스키마 포함) |
| 5 | **정비 잠금:** soft-PLC 정비 잠금 상태, 원격 요청 거부, LOCAL 해제, CMMS 작업지시 완료 조건에 잠금 확인 (G11) | R1~R3(법)의 교육용 흉내 |
| 6 | **외부 출처 넓히기:** 생산 작업 지시·설정값 변경·정비 작업지시 + AI 권고(사람이 변환) (G10) | 의뢰서 §9 |
| 7 | **OT 이력:** FUXA DAQ(SQLite) 켜기. 원시 태그 InfluxDB를 DMZ로 옮기는 안은 선택 (G9) | R12, R6(예시) |
| 8 | **Kafka 역할 한정:** IT 쪽 요청 장부·감사. OT 안에는 없음 (G7) | R13, §4-3 |
| 9 | **감사:** 같은 요청 ID로 요청→승인→경계→수용→결과, 주체를 사람/시스템/AI로 구분 (G12) | R11·R15, CISA AI-OT |
| 10 | **격리 실습·연결 목록 문서** (G13·G14) | R12·R10 |
| 선택 | DMZ가 IT로도 연결을 열지 않게(IT 쪽 수집기·발송기) (G8) | CISA DiD "경로는 DMZ에서 끝남"(판단, 약함) |

---

## 확인 못 한 것

1. **NAMUR NE 178 본문**(유료). 검증 단계 이름, "최종 권한은 CPC"라는 문장 자체는 초록에 없다. 12번의 "최종 권한은 CPC에 남는다"는 초록보다 강한 표현이다 → 초록 수준("가용성·안전에 나쁜 영향 없이", "요청자와 공장 소유자 분리")으로만 쓴다.
2. **IEC 62443-3-3 SR 본문**(유료). SR 이름은 목차로 확인, RE 내용(SR 5.2 RE1 기본 거부가 SL2부터 등)은 벤더 해설로만 봄.
3. **KISA 「OT 환경의 제로트러스트 적용 안내서」 본문.** 보도자료만 읽음. KISA 스마트공장 보안모델은 **요약본**만 읽음(전체본은 이메일 요청).
4. **MES를 OT(L3)에 두는가 DMZ에 두는가의 현업 비율.** Purdue 기본형(L3)과 KISA 모델(외부 연계 MES는 Industrial DMZ)이 다르다. 비율 자료 없음.
5. **외부 시스템에서 설비로 가는 조치의 현업 비율**(작업 지시 인터페이스 사용률, OPC UA Job Control·Machinery Job Management 도입률). 찾지 못함.
6. **APC 설정값 쓰기의 표준 문장**(워치독·통신 끊김 시 로컬 설정값 복귀 등). 벤더·엔지니어링 회사 글만 있었다 [벤더 홍보] https://www.merobix.com/blog/what-is-a-communications-watchdog (2026-07-26, "drives its outputs to a configured safe state rather than holding the last command indefinitely", 원문 확인). 표준 근거는 찾지 못함.
7. **"OPC UA PubSub Actions over MQTT로 NE 178 구현" IEEE 논문 본문**, OPC UA Part 14 Actions 절 본문(검색 발췌만).
8. **CMMS가 PLC에 직접 쓰는 현업 사례·표준.** 찾지 못함(없다고 단정하지 않음).
9. **Odoo 20.0 Community, asyncua + ISA-95 Job Control 노드셋, 라우터 컨테이너 방향 강제의 실행·메모리.** 문서·저장소만 확인했고 실행하지 않았다.
10. **ISA-95 Part 5 본문**(유료). 거래 동사는 MESA B2MML 스키마 이름으로만 확인.
11. **MQTT 5 메시지 만료로 늦은 요청을 버리는 방식이 Mosquitto 브리지를 지나도 유지되는지.** 확인 안 함 → 만료는 메시지 본문의 시각으로 OT 수신기·PLC가 검사하는 것으로 설계한다(판단).
