# 구역 사이 방화벽(라우터) — 여러 망(ot·dmz·it)에 붙는 유일한 컨테이너(HANDOFF §2-1 ⑫, 17번 B7·B8)
FROM alpine:3.24
RUN apk add --no-cache iptables iproute2
COPY rules.sh /rules.sh
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD iptables -t nat -S PREROUTING | grep -q DNAT
ENTRYPOINT ["/bin/sh", "/rules.sh"]
