# 제조 문서 조사 원장

## 현업 시스템 설계 근거 — 2026-09-21 확인

- IEC 62682:2022, Edition 2.0, 발행 2022-12-08. 공식 공개 설명은 알람이 이상 조건을 알리고 작업자의 대응을 지원하며 이력과 외부 시스템 연계를 포함한다고 설명한다. https://webstore.iec.ch/en/publication/65543 . 유료 표준 본문은 확보하지 않았고 세부 조항 준수를 주장하지 않는다. SCADA 알람 이후의 조사·근거·대응 지원이라는 범위 판단에 사용한다. 공개 페이지의 stability date는 2027이며 이를 새 개정의 발행일로 표현하지 않는다.
- OPC UA for Machinery Part 1, 공식 참조 페이지 표시 v1.04.1. §5의 설비/구성요소 식별, 모니터링, 상태·건전성·공정 정보 구분을 확인했다. https://reference.opcfoundation.org/specs/OPC-40001-1/5 . Asset/Sensor 식별과 운전 상태·관측 이력 구분의 설계 참고다. 현재 AR-100은 Modbus 기반이며 OPC UA 인증 구현이라고 표현하지 않는다.
- 위 자료는 현재 제공 중인 공식 자료의 확인 기록이다. 제조 현장 검증이나 규격 인증을 대신하지 않으며, AR-100 임계치와 10초 신선도 같은 교육용 설정을 이들 규격에서 가져왔다고 주장하지 않는다.

## INOXPA-BCI — 현재 제조사 배포 원문 확보

- URL: https://www.inoxpa.com.au/uploads/document/Manuals%20de%20instruccions/Components/Mescla/BCI/20.005.30.01EN.pdf
- 제조사 제품 페이지의 문서 게시일: 2025-10-01. 실제 PDF 표지·바닥글 개정: **(B) 2024/08**, 20.005.30.01EN, 24쪽. 게시일을 문서 개정일로 표기하지 않는다.
- 2026-09-21 실제 다운로드, p.15 troubleshooting 표를 텍스트와 렌더 이미지로 대조했다. 액위·축·임계속도·베어링 후보가 진동/소음 열에 연결됨을 확인했다.
- 원문 보관: `_references/manufacturing-ai/manuals/INOXPA-BCI-20.005.30.01EN.pdf`. 원문 전체를 배포 패키지에 자동 포함하지 않는다.
- BCI는 AR-100에 장착한 실물 모델이 아니다. 문제를 다중 근거로 구분하는 원리에 참고하며 모터 정격·회전수·탱크 용량·부품 교체 지시를 그대로 이식하지 않는다.
- 교육용 작성물: `knowledge-docs/AR100-MIXER-RESPONSE.md`, `AR100-EVIDENCE-POLICY.md`, `AR100-ASSET-CONTEXT.md`. 결정적 추출과 검토 게시, 실제 사건의 문서 조회는 검증했다. 이후 실제 LLM 후보 생성·추론도 검증했으며 실행별 근거는 CURRENT-ACCEPTANCE.md를 따른다.
- Alfa Laval의 2025-05 개정판 후보를 찾았으나 확인한 assets URL들은 웹 도구 오류/직접 다운로드 BlobNotFound로 확보하지 못했다. 최신판을 읽었다고 주장하지 않는다. 2022 참고자료와 현재 배포 INOXPA 원문을 구분한다.

## AL-ALS-2022 — 범위 제한 참고 자료

- 제목: Alfa Laval Agitator ALS / ALB ATEX Instruction Manual.
- 식별자/개정: 100000818-EN3, 2022-10. 2026-09-21 확인. 검색 수집일과 발행일을 혼동하지 않는다. 최신판 여부는 미확인.
- URL: https://www.alfalaval.com/globalassets/documents/products/fluid-handling/mixing-equipment/agitators/als/instruction-manual---alfa-laval-agitator-als_alb-atex-100000818en.pdf
- 확인 범위: 표지, intended use, operation/control, troubleshooting의 웹 추출 텍스트. 표 원문 이미지 검토는 미완료.
- 참고할 원리: 운전 조건과 장비 명세의 일치 확인, 진동 이상에 복수 원인 존재, 정비와 운전 상태 확인 구분.
- 적용 제한: AR-100/M-101은 Alfa Laval 해당 제품이 아니다. ATEX 조건, 회전수·온도·정비 간격·정지 절차를 가상 설비의 검증된 규격으로 전용하지 않는다.
- 다음 확인: 현재 제조사 제품 페이지에서 더 최신 개정/상부 교반기 매뉴얼 확보. `assets.alfalaval.com/documents/p4f482cec/alfa-laval-agitator-alt-atex-instruction-manual-en.pdf`는 웹 도구 Internal Error로 아직 미독.

## SCADA 자체 사실

- `plant.yaml`: 가상 공정 태그·단위·명령·물리모델·고장 조건.
- `04_tier1_cep.sql`: 전류 9.6 A 초과 후 10초 이내 진동 7.1 mm/s 초과의 CEP_BEARING 규칙. 제조사 범용 한계치로 표현하지 않는다.
- `01_sources.sql`: 원본에는 quality와 ns ts 존재. 알람에는 quality·event_id·asset_id 필드가 없어 AI 수신 계층이 원본 조회/식별/대상 매핑을 수행해야 한다.
- `plant.py`: 고장 만료/clear로 bearing_wear가 초기화될 수 있다. 수치 복귀만으로 정비 완료라고 보고할 수 없다.

## 초기 시나리오 설계 방향 — 후속 실행 결과는 인수표 참조

대표 사건은 교반기 복합 알람. AI는 이상 재검출보다 관측 이력·적용 절차·추가 확인·승인·조치 결과를 관리한다. 대조 사건은 데이터 부족, 문서 적용 불일치, 승인 반려, 실행 결과 불명확, 고장 만료에 따른 자연 복귀를 포함한다. 실제 현업 자료 조사 및 시뮬레이터 실행 결과에 따라 구체화한다.
