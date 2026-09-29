# V2 수집기 이미지: 공식 Telegraf 1.40.1 + 디스크 버퍼 폴더(telegraf 사용자 소유).
# 공식 이미지에는 버퍼 폴더가 없어, 이름 볼륨을 붙이면 root 소유가 되어 telegraf(uid 100)가 쓰지 못한다(대장·땜빵 점검표 #9).
# 폴더를 이미지에 telegraf 소유로 만들어 두면 빈 이름 볼륨이 처음 붙을 때 소유권이 그대로 복사된다.
FROM telegraf:1.40.1-alpine
RUN mkdir -p /var/lib/telegraf-buffer && chown telegraf:telegraf /var/lib/telegraf-buffer
