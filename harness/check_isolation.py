"""실험 스택 격리 검사.

`.env.rotation`으로 렌더링한 compose 설정에 원본 V1의 흔적(컨테이너명, 27xxx·28xxx 호스트 포트,
원본 포트를 가리키는 환경변수·빌드 인자)이 남아 있으면 실패한다. 실험 스택을 띄우기 전에 실행한다.

    python harness/check_isolation.py            # 실험 설정 검사 → 누출 0이어야 통과
    python harness/check_isolation.py --original # 원본 설정 검사 → 누출이 잡혀야 검사기 정상
"""
import json
import os
import re
import subprocess
import sys

ORIGINAL_PORT = re.compile(r"^2[78]\d{3}$")
ORIGINAL_URL = re.compile(r":2[78]\d{3}")


def render(args):
    env = dict(os.environ, COMPOSE_PATH_SEPARATOR=":")
    result = subprocess.run(["docker", "compose", *args, "config", "--format", "json"],
                            capture_output=True, text=True, encoding="utf-8", env=env)
    if result.returncode:
        sys.exit(result.stderr)
    return json.loads(result.stdout)


def leaks(config, label):
    found = []
    for name, service in config["services"].items():
        container = service.get("container_name")
        if container and not container.startswith("rot-"):
            found.append((label, name, "container_name", container))
        for port in service.get("ports", []):
            if ORIGINAL_PORT.match(str(port.get("published", ""))):
                found.append((label, name, "port", port["published"]))
        for key, value in (service.get("environment") or {}).items():
            if isinstance(value, str) and ORIGINAL_URL.search(value):
                found.append((label, name, "env", key))
        for key, value in ((service.get("build") or {}).get("args") or {}).items():
            if ORIGINAL_URL.search(str(value)):
                found.append((label, name, "build_arg", key))
    for key, network in config.get("networks", {}).items():
        if network.get("name") in {"iiot", "ar100-ai_default"}:
            found.append((label, "-", "network", network["name"]))
    return found


def main():
    original = "--original" in sys.argv
    rotation = [] if original else ["--env-file", ".env.rotation"]
    scada = render(["--env-file", ".env", *rotation])
    ai = render(["-p", "ar100-ai" if original else "rot-ai", "--env-file", "ai-layer/.env.local", *rotation,
                 "-f", "ai-layer/compose.yml", "-f", "ai-layer/compose.scada.yml", "--profile", "knowledge"])
    found = leaks(scada, "scada") + leaks(ai, "ai")
    for item in found:
        print("LEAK", *item)
    print(f"leaks={len(found)}")
    if original:
        sys.exit(0 if found else "검사기 이상: 원본 설정에서 누출을 하나도 찾지 못했습니다.")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
