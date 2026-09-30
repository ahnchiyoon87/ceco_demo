"""AR-100 HMI 배치. 값은 OT 허브(UNS)에서, 조작은 …/cmd/operator 로(받을지는 PLC 가 정한다)."""


def render(d):
    static, txt, box, line, value, text_value, semaphore_box, motor, valve, button, number_input = (
        d[name] for name in ('static', 'txt', 'box', 'line', 'value', 'text_value', 'semaphore_box',
                             'motor', 'valve', 'button', 'number_input'))
    S, ST, CMD, PEND, DEC, ALERT, REG = d['SENSOR'], d['STATE'], d['CMD'], d['PENDING'], d['DECIDE'], d['ALERT'], d['REG']
    muted = '#9badc3'
    tag = {t['tag']: t for t in REG['tags']}
    p_limit = tag['PT-101']['usl']
    ranges_p = [{'type': 'range', 'min': -999, 'max': p_limit, 'color': '#233e54'},
                {'type': 'range', 'min': p_limit, 'max': 6.5, 'color': '#a35312'},
                {'type': 'range', 'min': 6.5, 'max': 999, 'color': '#a6373c'}]
    on_off = [{'type': 'range', 'min': -1, 'max': 0.5, 'color': '#5a6b7d'}, {'type': 'range', 'min': 0.5, 'max': 2, 'color': '#2f9e6e'}]
    alarm_flag = [{'type': 'range', 'min': -1, 'max': 0.5, 'color': '#1d3246'}, {'type': 'range', 'min': 0.5, 'max': 2, 'color': '#b3363a'}]
    ok_flag = [{'type': 'range', 'min': -1, 'max': 0.5, 'color': '#b3363a'}, {'type': 'range', 'min': 0.5, 'max': 2, 'color': '#1f6f58'}]
    static('<rect width="1600" height="1180" fill="#0b1422"/>')
    txt(32, 40, 'AR-100 / PROCESS CONTROL (OT)', size=13, fill='#60d4bd', weight='600')
    txt(32, 78, '반응기 라인 · 공정 감시', size=28, weight='600')
    txt(1568, 42, '가상 공정 · 교육용', size=14, fill=muted, anchor='end')
    txt(1568, 73, '계측: OT 허브(UNS) 구독  /  조작: soft-PLC 운전원 채널', size=13, fill=muted, anchor='end')

    # 01 공정 흐름
    box(28, 106, 990, 374, fill='#111f30', stroke='#2a4058', rx=14)
    txt(50, 137, '01  공정 흐름', size=16, weight='600')
    txt(996, 137, '원료 → 이송 → 교반·가열 → 배출', size=13, fill=muted, anchor='end')
    box(65, 199, 136, 177, fill='#172e43', stroke='#6089aa', rx=18)
    txt(133, 187, 'TK-101 원료', size=14, anchor='middle')
    txt(133, 248, '레벨', size=12, fill=muted, anchor='middle')
    value(183, 282, S['LT-101'], '%', size=22)
    line(201, 334, 270, 334, c='#4982a1')
    motor(294, 337, 23, S['IT-101'], [
        {'type': 'range', 'min': '-1', 'max': '0.5', 'color': '#63758a'},
        {'type': 'range', 'min': '0.5', 'max': str(tag['IT-101']['usl']), 'color': '#42c9ad'},
        {'type': 'range', 'min': str(tag['IT-101']['usl']), 'max': '999', 'color': '#e97868'}])
    txt(294, 385, 'P-101 공급펌프', size=13, fill=muted, anchor='middle')
    line(318, 334, 403, 334, c='#4982a1')
    box(403, 213, 300, 200, fill='#172e43', stroke='#6089aa', rx=22)
    txt(553, 197, 'R-101 교반 반응기', size=15, anchor='middle')
    static('<path d="M550 216V263 M523 261H580" fill="none" stroke="#729bb7" stroke-width="6"/>')
    txt(426, 299, '온도', size=12, fill=muted)
    value(680, 301, S['TT-101'], '°C', size=22)
    semaphore_box(414, 310, 278, 45, S['PT-101'], ranges_p)
    txt(426, 342, '압력', size=12, fill='#ffffff')
    value(680, 344, S['PT-101'], 'barg', size=22, color='#ffffff')
    txt(426, 385, '레벨', size=12, fill=muted)
    value(680, 387, S['LT-102'], '%', size=22)
    line(703, 334, 782, 334, c='#4982a1')
    valve(805, 337, 20, ST['valve_sp'], [
        {'type': 'range', 'min': '-1', 'max': '5', 'color': '#63758a'},
        {'type': 'range', 'min': '5', 'max': '70', 'color': '#60b5cf'},
        {'type': 'range', 'min': '70', 'max': '101', 'color': '#42c9ad'}])
    line(828, 334, 955, 334, c='#4982a1')
    txt(805, 386, 'CV-101 배출밸브', size=13, fill=muted, anchor='middle')
    txt(950, 317, '제품 →', size=15, anchor='end')
    txt(52, 454, '값은 엣지가 OT 허브에 낸 UNS 값입니다(품질이 STALE 이면 마지막 값). 통신 경고 중에는 조작하지 마세요.', size=12, fill=muted)
    txt(52, 473, f'압력 색상: 남색 정상 / 주황 {p_limit:g} barg 이상 / 빨강 6.5 barg 이상(PLC 인터록)', size=12, fill='#e4b987')

    # 02 운전원 조작 · 모드
    box(1038, 106, 534, 374, fill='#111f30', stroke='#2a4058', rx=14)
    txt(1060, 137, '02  운전원 조작', size=16, weight='600')
    txt(1060, 160, '명령은 PLC 가 모드·인터록·범위를 검사해 받습니다(REMOTE_MANUAL 에서만).', size=12, fill=muted)
    for y, label, key in [(176, 'P-101 공급펌프', 'pump'), (216, 'M-101 교반기', 'agitator'),
                          (256, 'HX-101 히터', 'heater'), (296, 'HX-102 냉각기', 'cooler')]:
        semaphore_box(1060, y + 6, 14, 14, ST[key], on_off, rx=7)
        txt(1084, y + 19, label, size=14)
        button(1260, y, 70, 30, '기동', CMD[key], 1, bg='#167e6a')
        button(1338, y, 70, 30, '정지', CMD[key], 0, bg='#a6504a')
    txt(1060, 360, '운전 모드', size=13, fill=muted)
    text_value(1150, 360, ST['mode'], size=15, color='#9fe3d2')
    button(1330, 342, 110, 28, 'MANUAL', CMD['mode'], 'REMOTE_MANUAL', bg='#315e82')
    button(1448, 342, 110, 28, 'AUTO', CMD['mode'], 'REMOTE_AUTO', bg='#4a5f96')
    txt(1060, 394, '정비 모드', size=13, fill=muted)
    semaphore_box(1140, 382, 14, 14, ST['maint'], alarm_flag, rx=7)
    txt(1162, 394, '담당자', size=12, fill=muted)
    value(1240, 394, ST['maint_op'], '', size=14, color='#ffd59e', dec=0)
    txt(1262, 394, 'ID 입력→정비 켜기', size=12, fill=muted)
    number_input(1448, 380, 110, 26, CMD['maint'])
    txt(1060, 424, '인터록', size=12, fill=muted)
    semaphore_box(1110, 413, 14, 14, ST['interlock'], alarm_flag, rx=7)
    txt(1140, 424, '비상정지', size=12, fill=muted)
    semaphore_box(1200, 413, 14, 14, ST['estop'], alarm_flag, rx=7)
    txt(1230, 424, '현장 통신', size=12, fill=muted)
    semaphore_box(1295, 413, 14, 14, ST['field_comm'], ok_flag, rx=7)
    txt(1325, 424, 'PLC 통신', size=12, fill=muted)
    semaphore_box(1388, 413, 14, 14, ST['plc_comm'], ok_flag, rx=7)
    txt(1060, 456, '마지막 명령 응답', size=12, fill=muted)
    text_value(1180, 456, ST['ack'], size=13, color='#ffd59e')
    txt(1560, 472, '정비 해제는 현장 패널(해제 키)에서만', size=11, fill=muted, anchor='end')

    # 03 전체 계측
    txt(32, 519, '03  전체 계측', size=17, weight='600')
    txt(1568, 519, 'UNS 값 · 규격을 넘으면 공정 알람(FUXA 알람 목록)', size=12, fill=muted, anchor='end')
    for index, t in enumerate(REG['tags']):
        x, y = 28 + (index % 6) * 260, 541 + (index // 6) * 116
        if t['tag'] == 'PT-101':
            semaphore_box(x, y, 244, 101, S['PT-101'], ranges_p, rx=10)
        else:
            box(x, y, 244, 101, fill='#122236', stroke='#283e55', rx=10)
        txt(x + 15, y + 25, t['tag'], size=13, fill='#8fb4d2', weight='600')
        txt(x + 229, y + 25, t['desc'], size=11, fill=muted, anchor='end')
        unit = {'degC': '°C', 'm3/h': 'm³/h'}.get(t['unit'], t['unit'])
        value(x + 228, y + 69, S[t['tag']], unit, size=23, color='#ffffff' if t['tag'] == 'PT-101' else '#7fe3b0')

    # 04 설정값
    box(28, 785, 990, 117, fill='#111f30', stroke='#2a4058', rx=12)
    txt(48, 814, '04  설정값', size=16, weight='600')
    txt(990, 814, '흰 칸에 입력 → Enter → 오른쪽 현재 설정값 확인', size=14, fill='#e4b987', anchor='end', weight='600')
    for x, label, key, unit in [(48, '펌프 속도', 'pump_sp', '%'), (365, '밸브 개도', 'valve_sp', '%'), (682, '반응기 온도', 'temp_sp', '°C')]:
        txt(x, 844, label, size=12, fill=muted)
        number_input(x, 854, 110, 33, CMD[key])
        value(x + 277, 879, ST[key], unit, size=18, dec=1)

    # 05 분석 경고(참고) — 알람 목록과 따로, 소리·조작 없음
    box(1038, 785, 534, 117, fill='#231f2b', stroke='#594054', rx=12)
    txt(1058, 815, '05  분석 경고(참고)', size=16, weight='600')
    text_value(1058, 849, ALERT, placeholder='새 분석 경고 없음 · 정상 판정 아님')
    txt(1058, 882, 'IT 분석(Flink) 결과를 참고로 보입니다. 공정 알람이 아니며 조작하지 않습니다.', size=12, fill=muted)

    # 06 받은 요청(외부 시스템 = AI 의 작업 요청, REMOTE_MANUAL 에서 운전원이 수락·거부)
    box(28, 922, 1544, 196, fill='#1a2130', stroke='#43506a', rx=12)
    txt(48, 952, '06  받은 요청', size=16, weight='600')
    txt(190, 952, '외부 시스템(AI)이 담당자 승인을 거쳐 보낸 작업 요청입니다. REMOTE_MANUAL 에서는 여기서 운전원이 받을지 정합니다(60초 넘으면 자동 거부).', size=12, fill=muted)
    txt(48, 990, '대기', size=12, fill=muted)
    value(110, 990, PEND['count'], '건', size=16, color='#ffd59e', dec=0)
    txt(150, 990, '요청 ID', size=12, fill=muted)
    text_value(215, 990, PEND['head_job'], size=13, color='#cfe3ff')
    txt(48, 1022, '내용', size=12, fill=muted)
    text_value(110, 1022, PEND['head_desc'], size=15, color='#ffffff')
    txt(48, 1054, '원인', size=12, fill=muted)
    text_value(110, 1054, PEND['head_context'], size=13, color='#c9d3e0')
    txt(48, 1086, '대기 시간', size=12, fill=muted)
    value(170, 1086, PEND['head_wait_s'], '초', size=14, color='#ffd59e', dec=0)
    button(1300, 990, 120, 40, '수락', DEC['accept'], 1, bg='#167e6a')
    button(1432, 990, 120, 40, '거부', DEC['reject'], 1, bg='#a6504a')
    txt(1552, 1054, '수락해도 PLC 가 물리적으로 되는지 다시 검사합니다.', size=12, fill=muted, anchor='end')
    txt(32, 1150, '수집 → 엣지 → OT 허브(UNS) → (OT 가 연 브리지) → DMZ → IT(Kafka·Flink·AI). 이 화면은 OT 안에서만 돌며 IT 가 멈춰도 계속됩니다.', size=12, fill='#8caac2')
