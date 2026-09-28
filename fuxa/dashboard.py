"""Readable AR-100 HMI layout. All live items use the existing FUXA bindings."""


def render(draw):
    static, txt, box, line, value, semaphore_box, motor, valve, button, number_input, alert_text = (
        draw[name] for name in ('static', 'txt', 'box', 'line', 'value', 'semaphore_box',
                               'motor', 'valve', 'button', 'number_input', 'alert_text'))
    controls, cfg = draw['CTL'], draw['CFG']
    muted = '#9badc3'
    pressure_limit = next(t['usl'] for t in cfg['tags'] if t['name'] == 'PT-101')
    pressure_trip = cfg['physics']['interlock']['pressure_trip_barg']
    pressure_ranges = [
        {'type': 'range', 'min': -999, 'max': pressure_limit, 'color': '#233e54'},
        {'type': 'range', 'min': pressure_limit, 'max': pressure_trip, 'color': '#a35312'},
        {'type': 'range', 'min': pressure_trip, 'max': 999, 'color': '#a6373c'},
    ]
    static('<rect width="1600" height="1000" fill="#0b1422"/>')
    txt(32, 40, 'AR-100 / PROCESS CONTROL', size=13, fill='#60d4bd', weight='600')
    txt(32, 78, '반응기 라인 · 공정 감시', size=28, weight='600')
    txt(1568, 42, '가상 공정 · 교육용', size=14, fill=muted, anchor='end')
    txt(1568, 73, '계측: Modbus 직접 조회  /  분석: 수집 파이프라인', size=13, fill=muted, anchor='end')

    box(28, 106, 990, 374, fill='#111f30', stroke='#2a4058', rx=14)
    txt(50, 137, '01  공정 흐름', size=16, weight='600')
    txt(996, 137, '원료 → 이송 → 교반·가열 → 배출', size=13, fill=muted, anchor='end')
    # Vessel geometry is a schematic, never a simulated liquid-level reading.
    box(65, 199, 136, 177, fill='#172e43', stroke='#6089aa', rx=18)
    txt(133, 187, 'TK-101 원료', size=14, anchor='middle')
    txt(133, 248, '레벨', size=12, fill=muted, anchor='middle')
    value(183, 282, 'LT_101', '%', size=22)
    line(201, 334, 270, 334, c='#4982a1')
    motor(294, 337, 23, 'IT_101', [
        {'type':'range','min':'-1','max':'0.5','color':'#63758a'},
        {'type':'range','min':'0.5','max':str(next(t['usl'] for t in cfg['tags'] if t['name']=='IT-101')),'color':'#42c9ad'},
        {'type':'range','min':str(next(t['usl'] for t in cfg['tags'] if t['name']=='IT-101')),'max':'999','color':'#e97868'}])
    txt(294, 385, 'P-101 공급펌프', size=13, fill=muted, anchor='middle')
    line(318, 334, 403, 334, c='#4982a1')
    box(403, 213, 300, 200, fill='#172e43', stroke='#6089aa', rx=22)
    txt(553, 197, 'R-101 교반 반응기', size=15, anchor='middle')
    static('<path d="M550 216V263 M523 261H580" fill="none" stroke="#729bb7" stroke-width="6"/>')
    txt(426, 299, '온도', size=12, fill=muted)
    value(680, 301, 'TT_101', '°C', size=22)
    semaphore_box(414, 310, 278, 45, 'PT_101', pressure_ranges)
    txt(426, 342, '압력', size=12, fill='#ffffff')
    value(680, 344, 'PT_101', 'barg', size=22, color='#ffffff')
    txt(426, 385, '레벨', size=12, fill=muted)
    value(680, 387, 'LT_102', '%', size=22)
    line(703, 334, 782, 334, c='#4982a1')
    valve(805, 337, 20, 'ValveOpenSP', [
        {'type':'range','min':'-1','max':'5','color':'#63758a'},
        {'type':'range','min':'5','max':'70','color':'#60b5cf'},
        {'type':'range','min':'70','max':'101','color':'#42c9ad'}])
    line(828, 334, 955, 334, c='#4982a1')
    txt(805, 386, 'CV-101 배출밸브', size=13, fill=muted, anchor='middle')
    txt(950, 317, '제품 →', size=15, anchor='end')
    txt(52, 454, '수치는 수신된 태그 값입니다. 통신 단절 시 마지막 값이 남습니다. 연결 경고 중에는 조작하지 마세요.', size=12, fill=muted)
    txt(52, 473, f'압력 색상: 남색 정상 / 주황 {pressure_limit:g} barg 이상 / 빨강 {pressure_trip:g} barg 이상', size=12, fill='#e4b987')

    box(1038, 106, 534, 374, fill='#111f30', stroke='#2a4058', rx=14)
    txt(1060, 137, '02  운전원 조작', size=16, weight='600')
    txt(1060, 164, '버튼은 가상 설비에 직접 명령합니다. 아래 운전값을 확인하세요.', size=12, fill=muted)
    for y, label, key in [(180,'P-101 공급펌프','pump'),(224,'M-101 교반기','agitator'),(268,'HX-101 히터','heater'),(312,'HX-102 냉각기','cooler')]:
        txt(1060,y+22,label,size=14)
        button(1225,y,76,34,'기동',controls[key],1,bg='#167e6a')
        button(1312,y,76,34,'정지',controls[key],0,bg='#a6504a')
        value(1538,y+24,controls[key],'',size=18)
    txt(1540, 365, '운전값 1 = 기동 / 0 = 정지', size=12, fill=muted, anchor='end')
    txt(1060,400,'고압 인터록',size=14)
    value(1260,400,controls['interlock'],'',size=20,color='#ffb378')
    button(1386,378,154,36,'알람 확인 ACK',controls['ack'],1,bg='#315e82')
    txt(1060,437,'인터록 1 = 발동 · 해제 조건은 현장 로직이 판단',size=12,fill=muted)
    txt(1060,459,'정지 확인은 원인 제거·정비 완료를 뜻하지 않습니다.',size=12,fill=muted)

    txt(32, 519, '03  전체 계측', size=17, weight='600')
    txt(1568, 519, '같은 시점의 설비 상태 · 공정값과 AI 판단을 구분', size=12, fill=muted, anchor='end')
    for index, tag in enumerate(cfg['tags']):
        x, y = 28 + (index % 6) * 260, 541 + (index // 6) * 116
        if tag['name'] == 'PT-101':
            semaphore_box(x, y, 244, 101, 'PT_101', pressure_ranges, rx=10)
        else:
            box(x,y,244,101,fill='#122236',stroke='#283e55',rx=10)
        txt(x+15,y+25,tag['name'],size=13,fill='#8fb4d2',weight='600')
        txt(x+229,y+25,tag['desc'],size=11,fill=muted,anchor='end')
        unit = {'degC':'°C','m3/h':'m³/h'}.get(tag['unit'],tag['unit'])
        value(x+228,y+69,tag['name'].replace('-','_'),unit,size=23,
              color='#ffffff' if tag['name'] == 'PT-101' else '#7fe3b0')

    box(28,785,990,117,fill='#111f30',stroke='#2a4058',rx=12)
    txt(48,814,'04  설정값',size=16,weight='600')
    txt(990,814,'흰 칸에 입력 → Enter → 오른쪽 값 확인',size=14,fill='#e4b987',anchor='end',weight='600')
    for x,label,key,unit in [(48,'펌프 속도','pump_sp','%'),(365,'밸브 개도','valve_sp','%'),(682,'온도 ×10','temp_sp','')]:
        txt(x,844,label,size=12,fill=muted)
        number_input(x,854,110,33,controls[key])
        value(x+277,879,controls[key],unit,size=18)
    box(1038,785,534,117,fill='#231f2b',stroke='#594054',rx=12)
    txt(1058,815,'05  최근 분석 알람',size=16,weight='600')
    alert_text(1058,849,490)
    txt(1058,882,'Flink 분석 결과 · 원본 이력은 AI 운영 화면에서 확인',size=12,fill=muted)
    txt(32,940,'수집 → EdgeX · EMQX → Kafka → Flink → InfluxDB → AI 근거 분석 → 사람 검토',size=14,fill='#8caac2')
    txt(32,971,'이 화면은 Modbus 직접 관제입니다. 수집 파이프라인 전체의 정상 여부는 별도 상태·이력으로 확인하세요.',size=12,fill=muted)
