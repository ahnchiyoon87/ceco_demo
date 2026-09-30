# ═══════════════════════════════════════════════════════════════════════════
# soft-PLC: OpenPLC Runtime v4.2.4(MIT) + AR-100 제어 프로그램
#   1단계 compile — OpenPLC Editor v4.3.2(GPL-3.0)의 헤드리스 openplc-cli 로 ST 프로젝트(1_control/plc-openplc/project)를
#                   런타임 v4 묶음(STruC++ C++ 소스 + Modbus 설정)으로 만든다. 편집기는 이 단계에만 있다.
#   2단계 runtime — 공식 런타임 이미지 + 묶음 + 적재 스크립트(비어 있으면 REST 로 올리고 RUN)
# ═══════════════════════════════════════════════════════════════════════════
FROM debian:12-slim AS compile
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgtk-3-0 libnss3 libasound2 libgbm1 libxss1 libxtst6 \
      libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libpango-1.0-0 libcairo2 libatspi2.0-0 ca-certificates curl zip \
 && rm -rf /var/lib/apt/lists/*
ARG EDITOR_VERSION=4.3.2
ARG EDITOR_SHA256=2f964c3329eefdd50476d96c40c649193377d94e0bc0e8ebc0117f6c451a5b99
RUN curl -fsSL -o /tmp/editor.AppImage \
      "https://github.com/Autonomy-Logic/openplc-editor/releases/download/v${EDITOR_VERSION}/OpenPLC.Editor-${EDITOR_VERSION}.AppImage" \
 && echo "${EDITOR_SHA256}  /tmp/editor.AppImage" | sha256sum -c - \
 && chmod +x /tmp/editor.AppImage && cd /opt && /tmp/editor.AppImage --appimage-extract >/dev/null \
 && rm /tmp/editor.AppImage
COPY project /work/ar100-plc
# 컴파일 실패(종료 코드 4)는 빌드 실패로 둔다. 편집기는 쓰지 않는 EtherCAT 설정(빈 파일)을 늘 넣으므로 묶음에서 뺀다.
RUN cd /opt/squashfs-root \
 && ./open-plc-editor --no-sandbox --cli compile /work/ar100-plc --target "OpenPLC Runtime v4" --json > /tmp/compile.json 2>/tmp/compile.log \
    || (tail -40 /tmp/compile.log; exit 1) \
 && cd "/work/ar100-plc/build/OpenPLC Runtime v4/src" && rm -f conf/ethercat.json \
 && zip -qrX /program.zip . && sha256sum /program.zip | cut -d' ' -f1 > /program.sha256

FROM ghcr.io/autonomy-logic/openplc-runtime:v4.2.4
COPY --from=compile /program.zip /program.sha256 /opt/ar100/
# 런타임이 업로드 때 하는 일(플러그인 설정 반영·RETAIN 설정·C++ 컴파일·라이브러리 설치)을 빌드 때 런타임 자신의 코드로 한다.
# 그래서 이 이미지는 프로그램이 들어 있는 PLC 로 뜬다(컴파일 오류도 빌드에서 잡힌다).
# 영속 데이터 위치는 컨테이너에서 쓰는 /var/run/runtime(볼륨)으로 맞추고, 빌드 때 생긴 비밀값(.env)은 지운다.
ENV OPENPLC_PERSISTENT_DATA_DIR=/var/run/runtime
RUN set -e; cd /workdir; mkdir -p core/generated \
 && ./venvs/runtime/bin/python3 -c "import zipfile; zipfile.ZipFile('/opt/ar100/program.zip').extractall('core/generated')" \
 && ./venvs/runtime/bin/python3 -c "from webserver.plcapp_management import apply_retain_conf, update_plugin_configurations as u; apply_retain_conf('core/generated'); u('core/generated')" \
 && if ! bash ./scripts/compile.sh > /tmp/compile.log 2>&1; then tail -40 /tmp/compile.log; exit 1; fi \
 && bash ./scripts/compile-clean.sh >> /tmp/compile.log 2>&1 && ls build/libplc_*.so \
 && grep -E "^modbus_(slave|master),[^,]*,1," plugins.conf \
 && grep -q "^path=/var/run/runtime/retain.bin" retain.conf \
 && cp /opt/ar100/program.sha256 build/.ar100_program.sha256 \
 && rm -rf /var/run/runtime/.env /var/lib/openplc-runtime core/generated
COPY entrypoint.sh /opt/ar100/entrypoint.sh
ENTRYPOINT ["bash", "/opt/ar100/entrypoint.sh"]
