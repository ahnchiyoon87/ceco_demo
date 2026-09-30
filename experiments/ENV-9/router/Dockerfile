FROM alpine:3.24
RUN apk add --no-cache iptables iproute2
COPY rules.sh /rules.sh
ENTRYPOINT ["/bin/sh", "/rules.sh"]
