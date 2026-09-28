# Docker 용량과 다른 PC 배포

## 결론

현재 개발 PC 전체의 Docker 디스크를 다른 PC마다 똑같이 배정할 필요는 없다. SCADA 실행 이미지·초기 모델·필요한 데이터만 제공하고, 다른 프로젝트·개발 캐시·검증 DB는 제외한다. 아직 새 PC 최소 사양이나 동시 수강 인원 부하를 검증한 것은 아니다.

## 실제 측정

2026-09-23 변경 전 `docker_data.vhdx` 파일 길이는 **55.7 GiB**였다. 파일 길이와 파일시스템의 실제 할당 블록, Docker 설정의 최대 용량은 서로 다른 값이다. Docker 전체에 캡스톤·Ontology Studio·Supabase 등 다른 프로젝트가 들어 있어 SCADA 단독 요구량으로 사용하면 안 된다.

| 측정 | 결과 | 해석 |
|---|---:|---|
| 변경 전 Docker 전체 이미지 | 24.58 GB | 현재 SCADA 이외의 이미지 포함 |
| 그중 Docker가 미사용으로 분류한 이미지 | 12.45 GB | 다른 프로젝트를 다시 쓸 수 있으므로 일괄 삭제하지 않음 |
| 변경 전 빌드 캐시 | 12.18 GB / 회수 가능 0 B | 이미지와 공유되므로 전량 절감으로 계산 불가 |
| 첫 측정에서 실행 중인 컨테이너 | 30개 | SCADA + AI |
| 첫 컨테이너 메모리 스냅샷 합계 | 4.69 GiB | VM·호스트·순간 최대치·새 모델 빌드 부하 제외 |
| AI 이미지의 uv 다운로드 캐시 | 188 MiB | 실행에 불필요. Dockerfile에 UV_NO_CACHE=1 적용 |
| AI 가상환경 / LibreOffice 디렉터리 | 229 / 216 MiB | 실행 기능과 연관되어 임의 제거하지 않음 |

위 표는 변경 전/중 측정이다. 빌드가 진행되며 이미지·캐시가 달라진다. 최신 도구 출력은 [docker-storage.txt](docker-storage.txt), [docker-runtime.txt](docker-runtime.txt), [backend-image-components.txt](backend-image-components.txt)를 확인한다. 원래 이미지는 롤백 태그로 보존되어 있어 경량화 이미지를 만들었다고 현재 PC 디스크가 즉시 줄어들지는 않는다.

## 배포 대상에 따라 선택할 구성

1. **전체 파이프라인 실습**: EdgeX·MQTT·Kafka·Flink·InfluxDB·FUXA·AI 계층이 필요하다. 이 경우 다수 컨테이너는 현재 설계에 따른 것이며 단순 UI 하나의 자원 사용량이 아니다.
2. **경량 수집 실습**: 기존 `make lite`는 EdgeX를 우회해 시뮬레이터에서 MQTT로 직접 발행한다. 기능과 교육 범위가 달라진다. 이번 변경에서 lite+AI 전체 완주를 검증하지 않았으므로 바로 배포 검증 완료로 표시하지 않는다.
3. **대시보드 관람**: 운영 PC에서 구동하고 클라이언트는 브라우저로 볼 수 있다. 현재는 localhost 바인딩 및 로컬 시연 전제이며, 공개 접속·인증·다중 사용자 격리는 별도 작업이다. 임의로 외부에 열지 않았다.

신규 PC의 여유 공간 계획에는 **다운로드/압축 해제 이미지 + 초기 데이터 + 데이터 증가 + 업데이트 교체 공간**을 포함한다. 개발 캐시는 배포 필수품이 아니다. RAM은 위 스냅샷을 최저 요구량으로 쓰지 말고 실제 실습 부하를 측정해 결정한다.

## 줄이는 순서

- 빌드한 실행 이미지를 전달하고 수신 PC에서 개발 빌드를 반복하지 않는다. 모델 학습용 이미지는 모델 재학습이 없는 배포에서 제외할 수 있지만 `model.onnx` 등 초기 모델 제공과 초기화 절차를 먼저 검증해야 한다.
- 이번 Dockerfile 변경은 uv 다운로드 캐시를 이미지에 남기지 않는다. 잠금 파일과 설치 패키지는 유지한다.
- 컨테이너 로그 순환 및 InfluxDB/Kafka 보존 기간을 운영 목적에 맞춰 제한한다. 현행 Kafka 기본값은 24시간이며 sensor.alerts 생성 설정은 7일이다. InfluxDB 초기 설정은 30일이다. 기존 DB의 실제 보존 정책은 별도 확인하며 설정 파일 수정만으로 기존 DB가 바뀌었다고 간주하지 않는다.
- 다른 프로젝트 이미지·실습 데이터 삭제는 해당 프로젝트의 필요 여부를 먼저 확인한다. `docker system prune -a --volumes`를 기본 정리 명령으로 제공하지 않는다.
- VHDX 압축은 내부 미사용 공간이 생긴 뒤 별도로 검토한다. 현재 서비스 실행 중 강제 종료나 VHDX 조작을 하지 않았다.

Docker 공식 근거: [디스크 한도 설정](https://docs.docker.com/desktop/settings-and-maintenance/settings/), [선택적 정리](https://docs.docker.com/engine/manage-resources/pruning/), [빌드 캐시 GC](https://docs.docker.com/build/cache/garbage-collection/).
