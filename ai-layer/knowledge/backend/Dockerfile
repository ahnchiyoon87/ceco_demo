FROM python:3.12-slim

# uv 설치 (Python 패키지 관리를 uv로 통일)
RUN pip install --no-cache-dir uv==0.7.0

# LibreOffice: xlsx 스킬의 recalc.py에서 사용
# curl: 헬스체크
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice-calc curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./backend/

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

# 컨테이너 자체가 격리 경계이므로 샌드박스는 local 모드로 실행한다.
# 에이전트 명령은 이 컨테이너 안에서만 돌고 호스트 파일시스템에는 닿지 않는다.
ENV SANDBOX_BACKEND=local \
    LOCAL_SANDBOX_ROOT=/workspace \
    SANDBOX_WORKDIR=/workspace \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000

RUN mkdir -p /workspace/uploads /workspace/output && \
    cp -r /app/backend/skills /workspace/skills

EXPOSE 8000

CMD ["ontology-studio-backend"]
