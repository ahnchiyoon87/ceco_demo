# 15 · 무료 선택지 나란히 비교 — soft-PLC·엣지 연결·SCADA/HMI

- 작성일: 2026-09-29. 모든 지표의 확인일은 2026-09-29다.
- 목적: 14번 B1·B2·B4의 "무료 중 가장 낫다" 판단이 Docker 내려받기 수와 GitHub 별에만 기대던 약점을 보강한다.
- 관문(의뢰서 §1): PC 한 대·Docker·비용 0·BSL/SSPL/TSL/RCL/체험판 제외·2027-09-29 이후 지원·`latest` 금지.
- 근거 종류: [독립 설문] [공개 사례] [학술] [재단·저장소 지표] [벤더 홍보]. 원문을 못 읽고 검색 결과 요약만 본 것은 (검색 발췌). 못 찾은 것은 [미확인].
- GitHub 지표 읽는 법: 별·커미터·릴리스 수는 아래 [G]의 방법으로 얻었다(GitHub REST API 아님). "12개월 릴리스"는 2025-09-29 ~ 2026-09-29 사이 GitHub Releases 항목 수다(태그만 있고 Release가 없는 프로젝트는 적게 나온다).
- 학술 수치: Google Scholar는 자동 조회가 막혀 있어 건수 대신 **예시 논문**을 적는다. 건수를 적은 곳은 출처를 붙인다.


## 공통 출처 (아래 표에서 번호로 쓴다)

- [G] 저장소 지표: 별·라이선스·마지막 push = ecosyste.ms 저장소 API `https://repos.ecosyste.ms/api/v1/hosts/GitHub/repositories/<소유자>%2F<저장소>`. 커미터 수(전체/최근 1년) = `https://commits.ecosyste.ms/api/v1/hosts/GitHub/repositories/<소유자>%2F<저장소>` (ecosyste.ms가 커밋 이력에서 센 값. GitHub 화면의 "Contributors"와 조금 다를 수 있다). 릴리스 = `https://github.com/<소유자>/<저장소>/releases.atom`(최근 10건까지만 보인다. "≥10"은 10건 모두 12개월 안이라는 뜻). 확인 2026-09-29. GitHub REST API는 이 세션에서 호출 한도(시간당 60회)가 이미 소진되어 쓰지 못했다. 그래서 ecosyste.ms 집계와 릴리스 피드로 대신했다.
- [D] Docker Hub: `https://hub.docker.com/v2/repositories/<저장소>/tags` 와 `.../v2/search/repositories/?query=<이름>` (확인 2026-09-29).
- [OA] 학술 건수: OpenAlex `https://api.openalex.org/works?filter=title_and_abstract.search:<이름>` 의 `meta.count`(제목·초록에 이름이 나온 논문 수, 확인 2026-09-29). Google Scholar는 자동 조회가 막혀 쓰지 못했다. OpenAlex는 이름이 다른 뜻으로 쓰인 논문도 섞일 수 있어 **정확한 건수가 아니라 크기 비교용**이다.

## 1. soft-PLC

### 1-1. 비교 표

| 지표 | OpenPLC Runtime v4 | Eclipse 4diac FORTE (+4diac IDE) | Beremiz | (참고) OpenPLC v3 | (참고) RuSTy |
|---|---|---|---|---|---|
| 라이선스 | MIT (Runtime). Editor v4는 GPL-3.0 [G] | EPL-2.0 [G] | IDE GPL, 런타임 LGPL. 원문 "A Free Software IDE (GPL) and runtime (LGPL)" https://beremiz.org/ | GPL-3.0 [G] | LGPL-3.0 [G] |
| GitHub 별 | 368 (Editor v4 393) [G] | FORTE 74, IDE 81 [G] | 420 [G] | 1,516 [G] | 362 [G] |
| 커미터(전체/최근 1년) | 9 / 9 [G] | FORTE 64 / 15, IDE 91 / 35 [G] | [미확인] (ecosyste.ms 집계 없음) | 49 / 12 [G] | 27 / 11 [G] |
| 12개월 릴리스 · 마지막 릴리스 | ≥10 · v4.2.4 (2026-09-23) [G] | FORTE 5 · 3.3.0 (2026-09-08) [G] | 3 · 1.6.0 (2026-09-13) [G] | 0 · 저장소 archived [G] | 9 · 1.0.5 (2026-09-15) [G] |
| 저장소 생성 | 2025-08-08 (v4는 새 저장소) [G] | 2024-02-15 (GitHub 이전일. 프로젝트는 2007 시작) [G] | 2022-01-19 (GitHub 이전일. 프로젝트는 2007 시작) [G] | 2018-06-14 | 2019-11-23 |
| 재단 | 없음. 회사 Autonomy Logic 단독 [재단·저장소 지표] | Eclipse Foundation(Eclipse IoT) https://projects.eclipse.org/projects/iot.4diac | 없음 [미확인] | 없음 | 없음 |
| 표준 | IEC 61131-3. Editor v4가 LD·ST·FBD·SFC·IL 다섯 언어 지원(검색 발췌, https://autonomylogic.com/runtime). Runtime README 원문 "supporting IEC 61131-3 programming languages (Ladder Logic, Structured Text, Function Block Diagram, etc.)" | **IEC 61499**(분산 기능 블록). IEC 61131-3 PLC 언어 편집기가 아니다. 원문 "based on the IEC 61499 standard" https://eclipse.dev/4diac/ | IEC 61131-3 다섯 언어 + PLCopen XML 저장. 원문 "write Ladder (LD), Function Block Diagram (FBD), SFC, Instruction List (IL) and Structured Text (ST) programs" "store them as PLCopen XML" https://beremiz.org/ | IEC 61131-3 | ST 컴파일러만(런타임 아님) |
| 통신 | 플러그인 폴더에 `modbus_master`·`modbus_slave`·`opcua`(Python), `s7comm`·`ethercat`(C) 있음. https://github.com/Autonomy-Logic/openplc-runtime/tree/main/core/src/drivers/plugins (확인 2026-09-29) | Modbus TCP(libmodbus)·MQTT(Paho)·OPC UA(open62541) 통신 계층(검색 발췌, https://eclipse.dev/4diac/doc/communication/modbus.html) | "CANopen, Modbus, EtherCAT, OPC-UA, BACnet or MQTT" https://beremiz.org/ | Modbus·DNP3·EtherNet/IP(13번) | 해당 없음 |
| Docker | 공식 다중 아키텍처 이미지 `ghcr.io/autonomy-logic/openplc-runtime:v4.2.4`(14번 B1). README "Official multi-arch container images" | 공식 문서는 **이미지를 직접 빌드**하는 방법만 안내(https://eclipse.dev/4diac/doc/installation/docker.html). Docker Hub `4diac/forte` 태그는 `nightly` 하나, 2021-02-11 [D] → 사실상 없음 | 공식 이미지 못 찾음 [D][미확인] | 공식 없음(개인 이미지 `fdamador/openplc` 80,404회) [D] | 해당 없음 |
| 학술 [학술] | OpenAlex 제목·초록 **138건** [OA]. 대표 논문: Alves·Morris "OpenPLC: An IEC 61131-3 compliant open source industrial controller for cyber security research", Computers & Security 2018(OpenAlex 인용 82) https://doi.org/10.1016/j.cose.2018.07.007 · "IEC 61850 Compatible OpenPLC for Cyber Attack Case Studies on Smart Substation Systems", IEEE Access 2022(인용 27) https://doi.org/10.1109/access.2022.3144027 · LICSTER 교육·연구용 저가 ICS 시험대(OpenPLC 사용) https://arxiv.org/pdf/1910.00303 | OpenAlex 제목·초록 **88건** [OA]. 대표: "Framework for Distributed Industrial Automation and Control (4DIAC)", INDIN 2008(인용 111) https://doi.org/10.1109/indin.2008.4618110 · "Developing modular reusable IEC 61499 control applications with 4DIAC", INDIN 2013(인용 46) https://doi.org/10.1109/indin.2013.6622910 · "4DIAC in Teaching - Lessons from Lab Exercises and Student Projects"(검색 발췌, https://www.researchgate.net/publication/307995494) | OpenAlex 제목·초록 32건 [OA]이지만 동명 소설 인물 등 **잡음이 섞였다**(상위 4건 중 2건만 PLC). PLC 논문 예: "The Beremiz PLC: Adding Support for Industrial Communication Protocols", ETFA 2019 https://doi.org/10.1109/etfa.2019.8869526 · 원 논문 "An Open Source IEC 61131-3 Integrated Development Environment"(INDIN 2007) https://beremiz.org/collect/beremiz-paper-indin07.pdf | 위 OpenPLC 논문 대부분이 v3 대상 | — |
| 교육 사용(이름 있는 예) [공개 사례] | Western Carolina University 2학년 PLC 과목. 원문 "The OpenPLC open source PLC software [1] was chosen to support a PLC course for second-year students in an Electrical and Computer Engineering Technology program at Western Carolina University." (ASEE 2023, Paper #40286, PDF 원문 확인) https://peer.asee.org/teaching-industrial-control-with-open-source-software.pdf | TU Wien 석사 과목 실습, 학기당 약 120~130명(검색 발췌, 위 ResearchGate 논문). JKU Linz "4days of Eclipse 4diac" 겨울학교 2025-02-10~14, "3 ECTS" (원문 확인) https://eclipse.dev/4diac/events/4diacwinterschool/ | 논문·발표 목록에 St. Petersburg Polytechnic, University of Seoul 등이 있다고 검색 요약에 나옴(검색 발췌, https://beremiz.org/collect/) | (v3 기준, 위와 같음) | — |
| 산업 사용 | 회사 자체 클라우드 "Autonomy Edge"가 vPLC(= Runtime v4 컨테이너)를 배포한다고 설명 [벤더 홍보] https://autonomylogic.com/ . 이름 있는 공장 사례 못 찾음 [미확인] | 지원 기기 목록에 Bachmann M1, Phoenix Contact PLCnext, Revolution Pi, WAGO PFC200 등(검색 발췌, https://eclipse.dev/4diac/4diac_forte/). 이름 있는 공장 사례 못 찾음 [미확인] | 원문 "Commercial controllers, machines and research platforms already built on Beremiz" [벤더 홍보]. 회사 이름은 BLIIoT ARMxy 사례 페이지(제조사 자체 글, https://bliiot.com/cases-detail/the-open-source-plc-software-beremiz-on-the-beirei-technology-armxy-series) | — | — |
| 지원 정책 | 문서 없음 [미확인] → 롤링 | Eclipse 릴리스 기차. LTS 정책 [미확인] | [미확인] | EOL | [미확인] |

- 주의 1: OpenPLC의 학술·교육 근거는 **거의 모두 v3(지금은 archived)** 에 대한 것이다. v4는 2025-08에 새로 만든 저장소이고 커미터 9명이 모두 한 회사 쪽이다. "OpenPLC라는 이름의 계보"가 강한 것이지 v4 자체의 검증 기록이 긴 것은 아니다.
- 주의 2: 한 블로그(Industrial Monitor Direct)는 "Beremiz 개발이 2017년 이후 거의 멈췄다"고 적었으나(검색 발췌, https://industrialmonitordirect.com/blogs/knowledgebase/beremiz-open-source-iec-61131-3-ide-project-status-and-alternatives), GitHub에는 1.6.0(2026-09-13) 릴리스가 있다 [G]. 그 블로그 주장은 현재 사실과 다르다.
- 독립 설문(점유율)로 무료 soft-PLC를 비교한 자료는 찾지 못했다 [미확인].

### 1-2. 결론: 이 근거로 무엇을 쓴다

**OpenPLC Runtime v4.2.4를 쓴다(14번 B1 1안 유지).** 근거가 겹치는 곳이 여기뿐이다. ① 공식 Docker 이미지가 있는 유일한 후보다. ② IEC 61131-3 다섯 언어를 쓴다(현업 PLC 교육과 같은 언어). ③ Modbus 마스터·슬레이브와 OPC UA 플러그인이 저장소에 있다. ④ 학술 건수(OpenAlex 138 대 4diac 88 대 Beremiz 한 자리~수십)와 교육 과목(WCU) 근거가 셋 중 가장 크다. 다만 그 근거는 v3 계보라는 점, v4가 한 회사 단독이라는 점을 약점으로 남긴다. 4diac은 재단·대학 교육 근거가 가장 튼튼하지만 IEC 61499이고 Docker 이미지가 없어 **2순위(설명용)** 로 둔다. Beremiz는 Docker가 없어 제외한다.

### 1-3. 현업 상용과의 차이 (학생에게 설명할 것)

- 현업 공장의 제어기는 제조사 **전용 하드웨어 PLC**가 많다(판단. 점유율 수치는 이번에 찾지 않음 [미확인]). soft/virtual PLC 시장의 선두는 "Beckhoff, CODESYS, Phoenix Contact, Schneider Electric, Siemens"라고 분석 회사가 적었다(검색 발췌, https://iot-analytics.com/product/virtual-plc-and-soft-plc-market-2024-2030/, 14번 B1).
- 우리가 쓰는 OpenPLC는 **같은 IEC 61131-3 언어**(래더·ST 등)를 쓰고, Modbus로 설비를 읽고 쓴다. 그래서 "프로그램 구조·스캔 주기·입출력 매핑"은 현업과 같다.
- 다른 점: 안전 인증(SIL)·이중화·실시간 보장·제조사 기술지원이 없다. 현장 설비 제어에 그대로 쓰는 물건이 아니라 **구조를 배우는 도구**다.
- IEC 61499(4diac)는 "여러 제어기에 기능 블록을 나눠 배치하는" 차세대 표준이다. 아직 현업 주류는 아니다. 원문 "Today, this standard is not yet very widespread in the industry"(검색 발췌, https://eclipse.dev/4diac/).

## 2. 엣지 연결·프로토콜 변환

### 2-1. 비교 표 (관문 안 후보)

| 지표 | Node-RED 5.0.x (+node-red-contrib-modbus, node-red-contrib-opcua) | EdgeX Foundry 4.0.2 | Apache PLC4X 1.0.0 | Eclipse Kura 5.6.x | Telegraf 1.40.x | benthos-umh 0.16.x |
|---|---|---|---|---|---|---|
| 라이선스 | Apache-2.0. Modbus 노드 BSD-3-Clause, OPC UA 노드 Apache-2.0(npm 0.2.355, 2026-08-26) https://registry.npmjs.org/node-red-contrib-opcua [G] | Apache-2.0 [G] | Apache-2.0 [G] | EPL-2.0 [G] | MIT [G] | Apache-2.0 [G] |
| GitHub 별 | 23,693 (modbus 노드 347, opcua 노드 266) [G] | edgex-go 1,534 (device-modbus-go 120, device-opc-ua 34) [G] | 1,743 [G] | 582 [G] | 17,831 [G] | 62 [G] |
| 커미터(전체/최근 1년) | 277 / 29 (modbus 노드 28 / 2, opcua 노드 68 / 18) [G] | 127 / 14 [G] | 117 / 19 [G] | 68 / 10 [G] | 1,507 / 117 [G] | 23 / 10 [G] |
| 12개월 릴리스 · 마지막 | ≥10 · 5.0.7(2026-09-08, 14번) [G] | 정식은 4.0.2(2026-05-26 device 서비스 기준) 하나. edgex-go 피드의 ≥10은 `v4.1.0-dev.*` 개발 태그 [G] | 1.0.0(2026-09-07) 1건(이전 0.13.1은 2025-08-29) [G] | ≥10 · 5.6.2(2026-07-08) [G] | ≥10 · v1.40.1(2026-09-21) [G] | ≥10 · v0.16.0(2026-09-23) [G] |
| 재단 | OpenJS Foundation(2016 합류, At-Large)(검색 발췌, https://openjsf.org/blog/2021/09/08/why-satisfying-user-needs-is-not-a-zero-sum-game-an-interview-with-nick-oleary-node-red/) | LF Edge(리눅스 재단) https://lfedge.org/projects/edgex-foundry/ | Apache Software Foundation 최상위 프로젝트 | Eclipse Foundation(Eclipse IoT) https://projects.eclipse.org/projects/iot.kura | 없음(InfluxData 회사) | 없음(United Manufacturing Hub 회사) |
| Modbus 읽기+쓰기 | 예. 노드 목록에 `Modbus-Read`·`Modbus-Write`·`Modbus-Flex-Write` https://raw.githubusercontent.com/BiancoRoyal/node-red-contrib-modbus/master/package.json | 예. device profile에 Read/Write 동작(검색 발췌, https://docs.edgexfoundry.org/3.1/microservices/core/metadata/Ch-Metadata/) | 예(드라이버 읽기·쓰기, 릴리스 노트에 Modbus 쓰기 항목)(검색 발췌, https://github.com/apache/plc4x/blob/develop/RELEASE_NOTES) | 오픈소스 문서의 드라이버 목록에 Modbus가 없다(OPC UA·S7comm 등만). 상용판 ESF에 Modbus 드라이버(검색 발췌, https://eclipse-kura.github.io/kura/docs-release-5.6/connect-field-devices/driver-and-assets/ , https://marketplace.eclipse.org/content/esf-modbus-driver) → [미확인] | **읽기만**. 쓰기 경로 없음(14번 B2) | 읽기만(input). 원문 요약 "supports reading from four types of registers"(검색 발췌, https://docs.umh.app/benthos-umh/input/modbus) |
| OPC UA 클라이언트 | 예(`OpcUa-Client`, `OpcUa-Item` 등) [G] | 예(`device-opc-ua`, Apache-2.0, 2026-08-17 push) [G] | 예 | 예. Eclipse Milo 기반 드라이버(검색 발췌, https://marketplace.eclipse.org/content/esf-opc-ua-driver) | 읽기만(opcua 입력) | 읽기(input) + 쓰기(output). "writes data into an OPC UA server"(검색 발췌, https://docs.umh.app/benthos-umh/output/opc-ua-output) |
| 저장 후 전달(store-and-forward) | 내장 없음(공식 문서에서 찾지 못함 [미확인]). 흐름으로 따로 만들어야 함(판단) | 예. App SDK `[Writable.StoreAndForward] Enabled/RetryInterval/MaxRetryCount` https://docs.edgexfoundry.org/4.0/microservices/application/sdk/details/StoreAndForward/ (검색 발췌) | 없음(라이브러리) | 예. DataService가 H2 저장소에 메시지를 두었다가 보냄 "storing published messages in a persistent store and send them over the wire at a later time"(검색 발췌, https://download.eclipse.org/kura/docs/api/5.6.0/apidocs/org/eclipse/kura/data/DataService.html) | 디스크 버퍼 `buffer_strategy="disk"`가 있으나 **실험 기능**이고 멈춤 이슈가 열려 있음(검색 발췌, https://github.com/influxdata/telegraf/issues/16314) | [미확인] |
| 장치 등록부·명령 API | 없음(흐름이 곧 설정) | 예. core-metadata(장치 등록) + core-command(명령 REST)(검색 발췌, 위 EdgeX 문서) | 없음 | 예. Asset·Channel 모델로 읽기·쓰기(위 Kura 문서) | 없음 | 없음 |
| MQTT | 기본 노드 | 메시지 버스·MQTT 내보내기 | 직접 없음 [미확인] | 클라우드 연결이 MQTT | 입력·출력 플러그인 | Benthos 출력 |
| Docker | 공식 `nodered/node-red:5.0.7`(14번) | 공식 `edgexfoundry/*:4.0.2`(14번) | 게이트웨이 이미지 없음. 라이브러리라 앱을 직접 만들어야 함 [D] | `eclipsekura/kura:5.6.2-ubi8-x86_64`(2026-07-08) [D] | 공식 `telegraf:1.40.1-alpine`(14번) | [미확인] |
| 지원 정책 | 5.x Active, 4.x EOL 2026-12-31 → 롤링(14번) | 4.0 LTS **2027-03 종료**, 다음 판 2027 봄 "예정"(14번) → 관문 탈락 | [미확인] | [미확인] | 롤링(14번) | [미확인] |
| 학술 [학술] | 예: "Modbus-OPC UA Wrapper Using Node-RED and IoT-2040 with Application in the Water Industry", IEEE 2018 https://ieeexplore.ieee.org/document/8524749/ · "Supervisory Control and Data Acquisition Approach in Node-RED", IoT 2020 https://doi.org/10.3390/iot1010005 (PMC 논문 참고문헌에서 원문 확인) · OpenAlex 건수 → 2-2 | 예: "Siemens and EdgeX IIoT Platforms: A Functional and Performance Evaluation", IEEE ICC 2023, University of Bologna(검색 발췌, https://cris.unibo.it/bitstream/11585/946333/5/IEEE_ICC23.pdf) · IIC OMPAI 시험대(자동차 제조) https://lfedge.org/iic-announces-1st-ompai-testbed-based-on-edgex-foundry/ | [미확인](2-2 참고) | [미확인](2-2 참고) | [미확인] | [미확인] |
| 교육 사용(이름 있는 예) | University of Extremadura, "First Steps on the Educational Use of Node-RED as Industrial 4.0 Middleware for Automation and Supervision Disciplines", INTED 2023(원문 확인: 과목 적용 분석이지 학생 결과 보고는 아님) https://library.iated.org/view/FOLGADO2023FIR · "Teaching Methodology for IoT Workshop Course Using Node-RED", IEEE 2018 https://ieeexplore.ieee.org/document/8530664/ (검색 발췌) | University of Limerick 시험대에서 EdgeX 사용(검색 발췌) | [미확인] | [미확인] | [미확인] | [미확인] |
| 산업 사용 | Opto 22 groov EPIC 제어기에 Node-RED 기본 탑재 "Node-RED is included in groov EPIC"(제조사 페이지, https://www.opto22.com/products/groov-epic-system/groov-epic-software/node-red) [공개 사례]. 커밋 이력에 Hitachi 소속 이메일 기여자 다수 [G] | LF 보도자료: Accenture, HP, Intel, TIBCO, Eaton, Wipro(표면 검사) 등 사용(검색 발췌, https://www.linuxfoundation.org/press/press-release/edgex-foundry-the-leading-iot-open-source-framework-simplifies-deployment-with-the-latest-hanoi-release-new-use-cases-and-ecosystem-resources) [재단 발표]. 상용 배포판 IOTech Edge Xpert | [미확인] | Eurotech ESF가 Kura 상용판 "a commercial, enterprise-ready edition of Eclipse Kura"(검색 발췌, https://esf.eurotech.com/) [벤더 홍보] | [미확인](IT 지표 수집 용도 혼재, 14번) | UMH 자체 제품 [벤더 홍보] |
| 설문 | Node-RED 2023 커뮤니티 설문(응답 780명, 프로젝트 자체 설문 → 독립 아님): "Modbus and OPC-UA, both industrial protocols, did see growth in usage from the 2019 survey" https://nodered.org/about/community/survey/2023/ (원문 확인). 제조업 비중 31.5%→40.3%는 FlowFuse 글(검색 발췌, https://flowfuse.com/blog/2023/05/node-red-community-survey-results/) | 없음 | 없음 | 없음 | 없음 | 없음 |

### 2-1b. 관문 밖이거나 보조인 후보 (짧게)

| 후보 | 지표 [G] | 빠지는 이유 |
|---|---|---|
| ThingsBoard IoT Gateway | Apache-2.0, 별 2,191, 커미터 103/25, v3.8.5(2026-09-17) | 게이트웨이는 Apache-2.0이지만 **ThingsBoard 서버에 붙는 구조**다. 서버 4.4가 BUSL 1.1로 바뀌었다(14번 B4, https://thingsboard.io/blog/one-thingsboard-source-available/). 단독 게이트웨이로 쓰는 공식 방법 [미확인] |
| EMQX Neuron | LGPL-3.0, 별 1,404 | OSS판은 OPC UA 등이 상용(14번 B2) |
| HiveMQ Edge | Apache-2.0, 별 167 | 태그 쓰기(southbound mapping)가 상용 기능(14번 B2) |
| Fledge(LF Edge) | Apache-2.0, 별 197, 최근 1년 커미터 2, 12개월 릴리스 0(마지막 v3.1.0 2025-07-15) | 활동이 거의 멈춤 |
| Apache StreamPipes | Apache-2.0, 별 750, 커미터 113/25, 0.98.0(2025-12-15) | 분석 플랫폼 전체라 무겁다. 엣지 게이트웨이 칸 하나로 쓰기엔 크다(판단) |
| automation-gateway(Eclipse Milo 기반) | GPL-3.0, 별 300, 커미터 5/2, v1.38.1(2026-03-31) | 개인 1인 중심 |
| Eclipse Milo | EPL-2.0, 별 1,391, v1.1.7(2026-09-09) | OPC UA **라이브러리**. 게이트웨이 제품이 아님(Kura·automation-gateway가 이것을 쓴다) |

### 2-2. 학술 건수 비교 [학술]

OpenAlex 제목·초록 검색 건수다 [OA]. 크기 비교용이다.

| 검색어 | 건수 | 비고 |
|---|---|---|
| "Node-RED" AND (industrial OR IIoT OR SCADA OR PLC) | **486** | 상위 인용: "Delay Estimation of Industrial IoT Applications Based on Messaging Protocols", IEEE TIM 2018(인용 119) https://doi.org/10.1109/tim.2018.2813798 · "Development of an IoT Based Open Source SCADA System for PV System Monitoring", CCECE 2019(인용 83) https://doi.org/10.1109/ccece.2019.8861827 |
| "Node-RED" (전체) | 2,017 | 가정·농업 IoT가 많이 섞임 |
| "EdgeX Foundry" | 33 | 예: "DSLs for Model Driven Development of Secure Interoperable Automation Systems with EdgeX Foundry", FDL 2021 https://doi.org/10.1109/fdl53530.2021.9568378 |
| "Telegraf" AND (industrial OR IIoT OR OPC) | 11 | "Telegraf" 단독 288건은 신문 이름 등 잡음이 많음 |
| "Eclipse Kura" | 9 | |
| "PLC4X" | 5 | 예: "Evaluation of PLC4X based Middleware as Integrator of Brownfield systems into Industrial Cyber-Physical Production Systems", IFAC 2022 https://doi.org/10.1016/j.ifacol.2022.04.231 |
| "Eclipse Milo" | 3 | |

- 읽는 법: Node-RED가 산업 맥락 논문에서 다른 후보보다 **한 자릿수 이상 많다**. 이것은 별·내려받기와 **다른 종류의 근거**라서 14번의 1위 판단을 보강한다.
- 한계: 논문에 이름이 나온 것과 공장에서 쓰는 것은 다르다. 독립 점유율 설문은 이번에도 찾지 못했다 [미확인].

### 2-3. 결론: 이 근거로 무엇을 쓴다

**Node-RED 5.0.x(+node-red-contrib-modbus 5.60.2, 필요 시 node-red-contrib-opcua 0.2.355)를 쓴다(14번 B2 1안 유지).** 근거가 네 종류로 겹친다. ① 학술: 산업 맥락 논문 486건으로 다음 후보(EdgeX 33)보다 크게 많다. ② 재단: OpenJS Foundation 소속이고 커미터가 277명(최근 1년 29명)이다. ③ 공개 사례: Opto 22 산업용 제어기에 기본 탑재된다. ④ 기능: Modbus 읽기·쓰기, OPC UA 클라이언트, MQTT가 모두 무료다. 약점도 분명하다. **저장 후 전달과 장치 등록부·명령 API가 없다.** 이 둘은 EdgeX가 가장 잘 갖췄고, 이름 있는 도입 회사(Eaton·Wipro 등, 재단 발표)도 EdgeX 쪽이 뚜렷하다. 그래서 EdgeX는 "4.0 LTS가 2027-03에 끝나는 관문 문제만 풀리면 되돌아갈 2안"으로 남긴다. Kura는 저장 후 전달·자산 모델이 있으나 오픈소스판 Modbus 드라이버가 [미확인]이고 학술 근거가 작다. PLC4X는 라이브러리라 컨테이너 한 칸으로 쓸 수 없다. Telegraf는 쓰기가 없다.

### 2-4. 현업 상용과의 차이 (학생에게 설명할 것)

- 현업의 엣지 연결 칸은 Kepware(KEPServerEX), Ignition Edge, Litmus Edge 같은 **상용 게이트웨이**가 흔하다는 해설이 많다. 다만 독립 점유율 수치는 찾지 못했다(14번 B2) [미확인].
- 상용 게이트웨이는 보통 **수백 가지 드라이버, 태그 일괄 가져오기, 저장 후 전달, 중앙 관리 화면**을 한 제품에 묶어 판다(판단. 제품별 원문은 이번에 확인 안 함 [미확인]).
- 우리 Node-RED는 같은 일(설비 읽기 → 변환 → MQTT 발행, 명령 쓰기)을 **흐름을 조립해서** 한다. 그래서 "무엇을 읽고, 어떻게 이름 붙이고, 어디로 보내는가"가 눈에 보인다. 교육에는 이 점이 장점이다.
- 빠진 것을 학생에게 말해 준다: ① 망이 끊기면 데이터를 쌓아 두었다 보내는 기능(저장 후 전달)이 기본으로 없다. ② 설비 목록을 등록부에서 관리하는 기능이 없다. 우리 패키지는 흐름을 자산 등록부(B11)에서 생성해 이 빈자리를 메운다(14번 B2 판단). ③ 현업에서는 이 칸을 EdgeX처럼 "등록부 + 명령 API + 저장 후 전달"이 있는 구조로 짓는 경우가 있다고 설명한다.

## 3. SCADA·HMI

### 3-1. 비교 표

| 지표 | FUXA 1.3.4 | Scada-LTS 2.8.0 | Rapid SCADA 6.5.0 | OpenRemote 1.31.x | Node-RED Dashboard 2 (1.32.0) |
|---|---|---|---|---|---|
| 라이선스 | MIT [G] | GPL-2.0 [G] | Apache-2.0(Standard). 추가 모듈은 유료가 섞임 "Additional software modules … open or proprietary"(검색 발췌, https://rapidscada.org/product/license/) | AGPL-3.0(LICENSE.txt 원문 "GNU Affero General Public License") https://raw.githubusercontent.com/openremote/openremote/master/LICENSE.txt | Apache-2.0 [G] |
| GitHub 별 | 5,059 [G] | 989 [G] | 452 [G] | 1,910 [G] | 355 [G] |
| 커미터(전체/최근 1년) | 77 / 29 [G] | [미확인](집계 없음) | [미확인](집계 없음) | 66 / 19 [G] | 50 / 20 [G] |
| 12개월 릴리스 · 마지막 | ≥10 · v1.3.4(2026-08-12) [G] | 1 · `v2.8.0_pre`(2025-10-23). Docker `v2.8.0`은 2025-10-17 이후 새 태그 없음 [G][D] | 5 · v6.5.0(2026-09-07) [G] | ≥10 · 1.31.1(2026-09-28) [G] | 6 · v1.32.0(2026-09-24) [G] |
| 재단 | 없음(frangoteam) | 없음(Abil'I.T. 회사) | 없음(Rapid SCADA 팀) | 없음(OpenRemote Inc.) | 없음(FlowFuse 회사. Node-RED 본체는 OpenJS) |
| MQTT 구독 | 예(공식 문서, 14번 B4) | 예. 소스에 `ds/messaging/protocol/mqtt`(와 amqp) https://github.com/SCADA-LTS/Scada-LTS/tree/develop/src/org/scada_lts/ds/messaging | 예. 공개 드라이버 `DrvMqttClient` https://github.com/RapidScada/scada-v6/tree/master/ScadaComm/OpenDrivers | 예(MQTT Agent) | 예(Node-RED 노드) |
| OPC UA 클라이언트 | 예. README "Modbus RTU/TCP, Siemens S7 Protocol, OPC-UA, BACnet IP, MQTT, Ethernet/IP …" https://raw.githubusercontent.com/frangoteam/FUXA/master/README.md | 소스 데이터소스 목록(bacnet·modbus·snmp·sql·http 등)에서 **OPC UA를 찾지 못함** https://github.com/SCADA-LTS/Scada-LTS/tree/develop/src/com/serotonin/mango/vo/dataSource [미확인] | 예. 공개 드라이버 `DrvOpcUa`(서버 쪽 `DrvDsOpcUaServer`도 있음) | **없음**. 프로토콜 에이전트 목록에 modbus·mqtt·knx·snmp 등만 있고 OPC UA 없음 https://github.com/openremote/openremote/tree/master/agent/src/main/java/org/openremote/agent/protocol | Node-RED OPC UA 노드로 가능 |
| 알람 상태(ISA-18.2 대비) | 발생·해제·확인(ACK)·미확인 복귀. **셸빙 없음**(14번 B4, 소스 확인) | 확인(acknowledged 시각·사용자)과 사용자별 "silenced". 등급 NONE·INFORMATION·URGENT·CRITICAL·LIFE_SAFETY. 셸빙 코드 못 찾음 https://raw.githubusercontent.com/SCADA-LTS/Scada-LTS/develop/src/com/serotonin/mango/rt/event/EventInstance.java | 이벤트 확인 `AckRequired`·`Ack`·`AckUserID`. 셸빙 못 찾음 https://raw.githubusercontent.com/RapidScada/scada-v6/master/ScadaCommon/ScadaCommon/Data/Models/Event.cs | 상태 OPEN·ACKNOWLEDGED·IN_PROGRESS·RESOLVED·CLOSED, 심각도 LOW~HIGH. 셸빙 없음 https://raw.githubusercontent.com/openremote/openremote/master/model/src/main/java/org/openremote/model/alarm/Alarm.java (업무 티켓형에 가깝다, 판단) | 알람 모델 없음(직접 흐름으로 구현, 판단) |
| 사용자 역할 | 사용자·그룹 권한(secureEnabled 켤 때)(검색 발췌, https://github.com/frangoteam/FUXA/wiki/Settings) | 데이터 포인트별 read/set 권한(검색 발췌, https://github.com/SCADA-LTS/Scada-LTS/issues/349) | 기본 역할 Administrator·Dispatcher·Guest·App(검색 발췌, https://rapidscada.net/docs/en/latest/configuration/user-management) | Keycloak 기반 RBAC·realm(검색 발췌, https://openremote.io/product/) | 다중 사용자 기능은 **FlowFuse 플랫폼 위에서만**(검색 발췌, https://flowfuse.com/blog/2024/01/dashboard-2-multi-user/) |
| Docker | 공식 `frangoteam/fuxa:1.3.4`, 내려받기 196,127 [D] | `scadalts/scadalts:v2.8.0`, 86,526 [D] | **공식 이미지 못 찾음**(GitHub Packages 비어 있음, 포럼 글만) https://github.com/orgs/RapidScada/packages · https://forum.rapidscada.org/?topic=docker-files | 공식 `openremote/manager:1.31.1`(2026-09-28), 288,796 [D] | Node-RED 이미지 안에 설치 |
| 학술 [학술] | OpenAlex "FUXA" 36건이지만 **곤충병 용어 등 잡음**이 대부분이라 쓸 수 없음 [OA]. 예: SIMPLE-ICS APT 시험대(2026)가 HMI로 FUXA를 썼다는 검색 요약(검색 발췌, https://arxiv.org/abs/2602.22082 — 초록에는 FUXA 언급 없음) | "Scada-LTS" OR "ScadaBR" **56건** [OA]. 예: "Assessing the impact of Modbus/TCP protocol attacks on critical infrastructure: WWTP case study", 2025 https://doi.org/10.1016/j.compeleceng.2025.110485 · ScadaBR 에너지 관리 논문 IEEE LA Trans 2016 https://doi.org/10.1109/tla.2016.7786305 | "Rapid SCADA" 8건 [OA]. 예: "The Modbus Protocol Vulnerability Test in Industrial Control Systems", CyberC 2020 https://doi.org/10.1109/cyberc49757.2020.00070 | 9건 [OA] | "Node-RED" AND (dashboard OR HMI) **504건** [OA](구 Dashboard 1 포함). 예: "Design and Implementation of an Open-Source SCADA System for a Community Solar-Powered Reverse Osmosis System"(Node-RED 대시보드+Grafana, 원문 일부 확인) https://pmc.ncbi.nlm.nih.gov/articles/PMC9781551/ |
| 교육 사용(이름 있는 예) | Udemy 유료 강좌 "FUXA SCADA Training"(대학 아님) https://www.udemy.com/course/fuxa-scada-training/ . 대학 과목 [미확인] | [미확인] | [미확인] | [미확인] | (2장 Node-RED 교육 사례와 같음) |
| 산업 사용 | Seeed reTerminal DM(산업용 패널 PC) 공식 위키가 FUXA 사용법 제공 https://wiki.seeedstudio.com/reTerminal-DM_intro_FUXA/ [벤더 홍보]. 이름 있는 공장 사례 [미확인] | 회사 주장 "water treatment operator modernized several aging SCADA systems"(회사명 없음)(검색 발췌, https://scada-lts.com/) [벤더 홍보] | Kazakhmys(카자흐스탄 구리 회사) 제련·선광 공장 적용(검색 발췌, https://rapidscada.org/projects/) [공개 사례(프로젝트 측 게시)] | City of Arnhem 에너지 관리(Interreg NWE 게시) https://vb.nweurope.eu/projects/project-search/cleanmobilenergy-clean-mobility-and-energy-for-cities/news/the-city-of-arnhem-goes-smart-with-openremote-s-energy-management-solution/ [공개 사례] — 공정 HMI가 아닌 에너지·스마트시티 | Opto 22 제어기의 Node-RED(2장) |
| 지원 정책 | 단일 라인, 정책 없음 → 롤링(14번) | [미확인] | [미확인] | [미확인] | [미확인] |

### 3-1b. 관문 밖 후보 (짧게)

| 후보 | 지표 | 빠지는 이유 |
|---|---|---|
| ThingsBoard CE | 별 22,464, 4.4 릴리스 2026-09-29 [G] | 4.4부터 BUSL 1.1, 4.3 LTS는 2027-07-20 종료(14번 B4) |
| Ignition Maker Edition | — | 비상업·개인 교육용 한정, 체험판은 2시간 단위(14번 B4) |
| ScadaBR | 별 155, 마지막 릴리스 2023-03-24, 최근 1년 커미터 0 [G] | 사실상 중단(Scada-LTS가 계보를 이음) |
| Rapid SCADA 5 | 마지막 v5.8.4(2021-11-15) [G] | 구판 |
| pvbrowser | 마지막 push 2023-10-17 [G] | 활동 없음 |

### 3-2. 결론: 이 근거로 무엇을 쓴다

**FUXA 1.3.4를 쓴다(14번 B4 유지).** 공정 HMI형 후보 가운데 **활동 지표가 가장 크고**(별 5,059, 최근 1년 커미터 29, 12개월 릴리스 10회 이상), 공식 버전 태그 이미지가 있고, MQTT 구독·OPC UA 클라이언트·Modbus를 모두 무료(MIT)로 가진 것은 FUXA뿐이다. 약점은 재단이 없고, 학술·산업의 이름 있는 근거가 약하다는 점이다(학술 건수는 잡음 때문에 셀 수 없었다). 근거의 겹침만 보면 **Rapid SCADA 6이 더 튼튼한 면이 있다**: Apache-2.0, OPC UA·MQTT 공개 드라이버, 이벤트 확인, 기본 역할, 이름 있는 공장 사례(Kazakhmys). 그러나 공식 Docker 이미지가 없어 "PC 한 대·Docker" 관문에서 직접 빌드가 필요하다. 그래서 **2안은 Rapid SCADA 6(자체 이미지 빌드 실측 후)** 으로 적는다. Scada-LTS는 12개월간 정식 릴리스가 없고 OPC UA를 소스에서 찾지 못해 내린다. OpenRemote는 OPC UA가 없고 IoT 플랫폼형이다. Node-RED Dashboard 2는 알람 모델이 없고 다중 사용자가 FlowFuse에 묶여 있다.

### 3-3. 현업 상용과의 차이 (학생에게 설명할 것)

- 현업 SCADA·HMI 선두는 Siemens(WinCC)·GE Digital·Rockwell(FactoryTalk)·Hitachi Vantara이고, 그다음이 Emerson·Yokogawa·Honeywell·ABB·Inductive Automation(Ignition)·AVEVA 등이다(ABI Research 2023, 14번 B4) [독립].
- FUXA도 화면 편집·태그 연결·알람·사용자 권한이라는 **같은 뼈대**를 가진다. 그래서 "태그 → 화면 → 알람 → 확인" 흐름은 현업과 같다.
- 다른 점: ① ISA-18.2의 **셸빙(일시 보류)·설계 억제·서비스 중지** 상태가 없다. 현업 상용 SCADA는 알람 관리 기능을 더 갖춘다(상용 제품별 원문은 이번에 확인 안 함 [미확인]). 우리는 알람 수명주기를 별도 칸(14번 X2)에서 설명한다. ② 이중화 서버·감사 추적·대형 태그 수·제조사 지원이 없다. ③ 현업은 한 회사 제품으로 PLC·HMI·히스토리언을 묶는 경우가 많다(판단).

## 확인 못 한 것

- **독립 설문(점유율)**: 세 층 모두 무료 제품끼리 비교한 독립 설문을 찾지 못했다. Node-RED 설문은 프로젝트 자체 설문이다.
- **Google Scholar 건수**: 자동 조회가 막혀 OpenAlex 건수로 대신했다. OpenAlex 건수에는 동명 잡음이 섞인다(Beremiz·Telegraf·FUXA는 특히 심함). FUXA의 실제 학술 사용 건수는 알 수 없다.
- **GitHub REST API 값**: 이 세션에서 호출 한도가 소진되어 쓰지 못했다. 별·커미터·릴리스는 ecosyste.ms 집계와 릴리스 피드로 얻었다. Beremiz·Scada-LTS·Rapid SCADA 6·OpenPLC Editor의 커미터 수는 집계가 없어 비웠다.
- **OpenPLC v4 자체의 학술·산업 사례**: 찾은 근거는 v3 계보다. v4(2025-08 새 저장소)의 이름 있는 공장 사례는 없다. OpenPLC Editor v4의 PLCopen XML 지원 여부도 원문 확인 못 함.
- **4diac의 이름 있는 산업 사례**: 지원 하드웨어 목록만 확인. 공장 이름은 못 찾음.
- **Kura 오픈소스판 Modbus 드라이버**: 문서 드라이버 목록에 없음. 상용 ESF에만 있는지 원문 확인 못 함.
- **PLC4X의 MQTT 연결·Docker 이미지**: 공식 게이트웨이 이미지를 찾지 못함.
- **benthos-umh의 저장 후 전달·공식 이미지 태그**: 확인 못 함.
- **Node-RED의 저장 후 전달**: 공식 문서에 내장 기능이 없다는 원문 확인은 못 함(찾지 못했다는 뜻).
- **대학 과목의 FUXA·Scada-LTS·Rapid SCADA·OpenRemote 사용 예**: 찾지 못함.
- **Scada-LTS OPC UA**: 소스 트리 목록에서 못 찾았을 뿐, 플러그인 형태 지원이 있는지 [미확인].
- **Rapid SCADA 6의 Docker**: 직접 이미지를 빌드해 도는지 실측하지 않았다(이번 작업은 도커 금지).
- **EdgeX 도입 회사 목록**: LF 보도자료 검색 요약으로만 확인. 각 회사 사례 원문은 읽지 않음.
- **지원 정책**: OpenPLC v4·4diac·Beremiz·Kura·PLC4X·Scada-LTS·Rapid SCADA·OpenRemote·Dashboard 2 모두 2027-09-29까지의 공식 지원 문서를 찾지 못했다. 관문은 롤링 해석(14번 §0)에 기대야 한다.
