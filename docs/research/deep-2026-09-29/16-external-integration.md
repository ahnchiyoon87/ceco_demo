# 16 · 외부 시스템 연결 — 밖으로 보내기와 설비 쪽으로 보내기

> 진행 중 (2026-09-30 작성 시작). 절을 끝낼 때마다 아래에 덧붙인다.

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

