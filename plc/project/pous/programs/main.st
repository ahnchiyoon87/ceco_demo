(* ═══════════════════════════════════════════════════════════════════════════
   AR-100 반응기 라인 제어 프로그램 (IEC 61131-3 ST, OpenPLC Runtime v4)
   이 파일은 registry/generate.py 가 plc/main.st.tmpl 에서 만든다. 손으로 고치지 않는다. 상수는 등록부·plant.yaml 이 정본이다.

   레지스터 지도
     %IW0..23   가상설비 계측 12점(float32, 2워드씩)  ← Modbus 마스터가 가상설비 HR0..23 에서 읽음
     %IW24..27  가상설비 스캔 순번·설비 시각(UINT32 2워드씩) — 계측값과 한 번에 읽음
     %IW300..308 현장 패널 스위치
     %QX0.0..0.3 구동기(펌프·교반기·히터·냉각기) → 가상설비 코일 0..3
     %QW100..102 설정값(펌프 %, 밸브 %, 온도 ×10) → 가상설비 HR100..102
     %QW103..118 상태·ACK (엣지가 설정값과 한 번에 읽어 UNS 에 발행)
     %MW0..1    시각 동기(epoch 초) — 엣지가 1초마다 씀
     %MW10..12  운전원 채널(FUXA → 엣지): 순번·명령 코드·값
     %MW20..27  외부 요청 채널(OT 수신기 → 엣지): 순번·코드·값·만료·운전원 수락·요청 해시

   명령 코드: 1 펌프 기동, 2 교반기 기동, 3 히터, 4 냉각기 (값 1=켬 0=끔)
              5 펌프 속도 %, 6 밸브 개도 %, 7 온도 설정 ×10, 10 운전 모드(1=REMOTE_MANUAL 2=REMOTE_AUTO), 11 정비 모드 켜기(값=담당자 ID)
   ACK 코드: 0 수용, 1 LOCAL_MODE, 2 MAINTENANCE, 3 MODE, 4 RANGE, 5 INTERLOCK, 6 EXPIRED, 7 DUPLICATE,
             8 UNKNOWN_COMMAND, 9 ESTOP, 10 NO_TIME_SYNC, 11 PHYSICS
   ═══════════════════════════════════════════════════════════════════════════ *)
PROGRAM main
  VAR
    (* ── 현장 장치 입력 ── *)
    lt101_hi AT %IW0 : WORD;  lt101_lo AT %IW1 : WORD;
    pt101_hi AT %IW8 : WORD;  pt101_lo AT %IW9 : WORD;
    it101_hi AT %IW14 : WORD; it101_lo AT %IW15 : WORD;
    it102_hi AT %IW16 : WORD; it102_lo AT %IW17 : WORD;
    seq_hi AT %IW24 : WORD;  seq_lo AT %IW25 : WORD;
    pts_hi AT %IW26 : WORD;  pts_lo AT %IW27 : WORD;
    fp_mode AT %IW300 : WORD;
    fp_local_seq AT %IW301 : WORD;
    fp_local_code AT %IW302 : WORD;
    fp_local_value AT %IW303 : WORD;
    fp_maint_on_seq AT %IW304 : WORD;
    fp_maint_release_seq AT %IW305 : WORD;
    fp_operator_id AT %IW306 : WORD;
    fp_estop AT %IW307 : WORD;
    (* ── 현장 장치 출력 ── *)
    q_pump AT %QX0.0 : BOOL;
    q_agitator AT %QX0.1 : BOOL;
    q_heater AT %QX0.2 : BOOL;
    q_cooler AT %QX0.3 : BOOL;
    q_sp_pump AT %QW100 : WORD;
    q_sp_valve AT %QW101 : WORD;
    q_sp_temp_x10 AT %QW102 : WORD;
    (* ── 상태·ACK ── *)
    st_run AT %QW103 : WORD;
    st_mode AT %QW104 : WORD;
    st_maint AT %QW105 : WORD;
    st_maint_op AT %QW106 : WORD;
    st_interlock AT %QW107 : WORD;
    st_field_comm AT %QW108 : WORD;
    st_estop AT %QW109 : WORD;
    st_outputs AT %QW110 : WORD;
    st_op_ack_seq AT %QW111 : WORD;
    st_op_ack_code AT %QW112 : WORD;
    st_rq_ack_seq AT %QW113 : WORD;
    st_rq_ack_code AT %QW114 : WORD;
    st_rq_ack_hash_hi AT %QW115 : WORD;
    st_rq_ack_hash_lo AT %QW116 : WORD;
    st_heartbeat AT %QW117 : WORD;
    st_fb_fault AT %QW118 : WORD;
    (* ── 엣지가 쓰는 명령 ── *)
    mw_time_hi AT %MW0 : WORD;  mw_time_lo AT %MW1 : WORD;
    op_seq AT %MW10 : WORD;  op_code AT %MW11 : WORD;  op_value AT %MW12 : WORD;
    rq_seq AT %MW20 : WORD;  rq_code AT %MW21 : WORD;  rq_value AT %MW22 : WORD;
    rq_exp_hi AT %MW23 : WORD;  rq_exp_lo AT %MW24 : WORD;
    rq_accepted AT %MW25 : WORD;
    rq_hash_hi AT %MW26 : WORD;  rq_hash_lo AT %MW27 : WORD;
  END_VAR
  VAR RETAIN
    maint : BOOL := FALSE;          (* 정비 모드는 재시작해도 유지(안전 쪽) *)
    maint_op : WORD := 0;
  END_VAR
  VAR
    init_done : BOOL := FALSE;
    mode : INT := 1;                (* 0 LOCAL, 1 REMOTE_MANUAL, 2 REMOTE_AUTO — 기동하면 REMOTE_MANUAL *)
    cmd_pump : BOOL := TRUE;
    cmd_agitator : BOOL := TRUE;
    cmd_heater : BOOL := TRUE;
    cmd_cooler : BOOL := FALSE;
    sp_pump : REAL := 60.0;
    sp_valve : REAL := 45.0;
    sp_temp : REAL := 72.0;
    interlock : BOOL := FALSE;
    estop : BOOL := FALSE;
    fb_fault_pump : BOOL := FALSE;
    fb_fault_agitator : BOOL := FALSE;
    field_comm_ok : BOOL := FALSE;
    time_ok : BOOL := FALSE;
    pt101 : REAL;  lt101 : REAL;  it101 : REAL;  it102 : REAL;
    seq_now : DWORD;  seq_prev : DWORD := 0;
    time_prev : WORD := 0;
    now_s : DWORD;
    pts : LREAL;  last_pts : LREAL := 0.0;  dpts : LREAL;
    ap_init : BOOL := FALSE;  ap_next : LREAL := 0.0;  ap_f : LREAL;
    tgt_pump : REAL;  tgt_valve : REAL;  tgt_temp : REAL;
    hold_pump : DINT := 0;  hold_valve : DINT := 0;  hold_temp : DINT := 0;
    rnd : DWORD := 16#2545F491;
    last_op_seq : WORD := 0;  last_rq_seq : WORD := 0;
    last_local_seq : WORD := 0;  last_maint_on_seq : WORD := 0;  last_maint_release_seq : WORD := 0;
    last_fp_mode : WORD := 1;
    seen_hash : ARRAY[0..7] OF DWORD;
    seen_idx : INT := 0;
    src : INT;  fresh : BOOL;  c_code : INT;  c_val : INT;  c_acc : BOOL;
    ok_code : BOOL;  is_stop : BOOL;  is_maint_on : BOOL;  local_ok : BOOL;  op_mode_cmd : BOOL;  start_or_change : BOOL;
    c_hash : DWORD;  c_exp : DWORD;  result : INT;  k : INT;
    heartbeat : WORD := 0;
    ton_comm : TON;  ton_time : TON;  ton_fb_pump : TON;  ton_fb_agit : TON;
  END_VAR

  (* ── 1. 입력 해독 ── *)
  pt101 := WORDS_TO_REAL(pt101_hi, pt101_lo);
  lt101 := WORDS_TO_REAL(lt101_hi, lt101_lo);
  it101 := WORDS_TO_REAL(it101_hi, it101_lo);
  it102 := WORDS_TO_REAL(it102_hi, it102_lo);
  seq_now := SHL(WORD_TO_DWORD(seq_hi), 16) OR WORD_TO_DWORD(seq_lo);
  pts := DWORD_TO_LREAL(SHL(WORD_TO_DWORD(pts_hi), 16) OR WORD_TO_DWORD(pts_lo));
  now_s := SHL(WORD_TO_DWORD(mw_time_hi), 16) OR WORD_TO_DWORD(mw_time_lo);

  (* ── 2. 현장 통신·시각 동기 감시 ── *)
  ton_comm(IN := (seq_now = seq_prev), PT := T#3s);
  field_comm_ok := (seq_now <> 0) AND NOT ton_comm.Q;
  seq_prev := seq_now;
  ton_time(IN := (mw_time_lo = time_prev), PT := T#5s);
  time_ok := (now_s <> 0) AND NOT ton_time.Q;
  time_prev := mw_time_lo;

  (* ── 3. 기동 초기화: 현장 장치 값을 한 번 읽은 뒤 현장 스위치·카운터를 기준으로 잡는다 ── *)
  IF NOT init_done AND seq_now <> 0 THEN
    IF fp_mode = 0 THEN mode := 0; ELSE mode := 1; END_IF;
    last_fp_mode := fp_mode;
    last_local_seq := fp_local_seq;
    last_maint_on_seq := fp_maint_on_seq;
    last_maint_release_seq := fp_maint_release_seq;
    last_op_seq := op_seq;
    last_rq_seq := rq_seq;
    init_done := TRUE;
  END_IF;

  IF init_done THEN
    (* ── 4. 비상정지(가상설비 안에서 제어와 독립으로도 동작) — 풀려도 저절로 다시 돌지 않게 명령을 끈다 ── *)
    estop := (fp_estop <> 0);
    IF estop THEN
      cmd_pump := FALSE; cmd_agitator := FALSE; cmd_heater := FALSE; cmd_cooler := FALSE;
    END_IF;

    (* ── 5. 현장 모드 선택 스위치: LOCAL 로 가면 LOCAL, REMOTE 로 돌아오면 늘 REMOTE_MANUAL ── *)
    IF fp_mode = 0 THEN
      mode := 0;
    ELSIF last_fp_mode = 0 THEN
      mode := 1;
    END_IF;
    last_fp_mode := fp_mode;

    (* ── 6. 정비 모드: 켜기는 현장 패널·운전원, 끄기는 현장 해제 키만 ── *)
    IF fp_maint_on_seq <> last_maint_on_seq THEN
      maint := TRUE; maint_op := fp_operator_id;
    END_IF;
    last_maint_on_seq := fp_maint_on_seq;
    IF fp_maint_release_seq <> last_maint_release_seq THEN
      maint := FALSE; maint_op := 0;
    END_IF;
    last_maint_release_seq := fp_maint_release_seq;

    (* ── 7. 현장 기동·정지 버튼: LOCAL 에서만 받는다 ── *)
    IF fp_local_seq <> last_local_seq THEN
      local_ok := (mode = 0) AND ((NOT estop) OR (fp_local_value = 0));
      IF local_ok THEN
        CASE WORD_TO_INT(fp_local_code) OF
          1: cmd_pump := (fp_local_value <> 0); fb_fault_pump := FALSE;
          2: cmd_agitator := (fp_local_value <> 0); fb_fault_agitator := FALSE;
          3: cmd_heater := (fp_local_value <> 0);
          4: cmd_cooler := (fp_local_value <> 0);
        END_CASE;
      END_IF;
    END_IF;
    last_local_seq := fp_local_seq;

    (* ── 8. 고압 인터록(히스테리시스). 결측 표시값은 판단에서 뺀다 ── *)
    IF pt101 > -1000.0 THEN
      IF pt101 >= 6.5 THEN
        interlock := TRUE;
      ELSIF pt101 <= 5.2 THEN
        interlock := FALSE;
      END_IF;
    END_IF;

    (* ── 9. 명령 두 출처 채널: 1 운전원(FUXA), 2 외부 요청(OT 수신기) ── *)
    FOR src := 1 TO 2 DO
      IF src = 1 THEN
        fresh := (op_seq <> last_op_seq);
        c_code := WORD_TO_INT(op_code); c_val := WORD_TO_INT(op_value); c_acc := FALSE;
        c_hash := 0; c_exp := 0;
      ELSE
        fresh := (rq_seq <> last_rq_seq);
        c_code := WORD_TO_INT(rq_code); c_val := WORD_TO_INT(rq_value); c_acc := (rq_accepted <> 0);
        c_hash := SHL(WORD_TO_DWORD(rq_hash_hi), 16) OR WORD_TO_DWORD(rq_hash_lo);
        c_exp := SHL(WORD_TO_DWORD(rq_exp_hi), 16) OR WORD_TO_DWORD(rq_exp_lo);
      END_IF;
      IF fresh THEN
        result := 0;
        ok_code := ((c_code >= 1) AND (c_code <= 7)) OR (c_code = 10) OR (c_code = 11);
        is_stop := (c_code <= 4) AND (c_val = 0);
        is_maint_on := (c_code = 11);
        op_mode_cmd := (c_code = 10) OR (c_code = 11);
        start_or_change := ((c_code <= 4) AND (c_val = 1)) OR ((c_code >= 5) AND (c_code <= 7)) OR (c_code = 10);
        (* 명령 코드·값 범위 *)
        IF NOT ok_code THEN
          result := 8;
        ELSIF c_code <= 4 AND (c_val < 0 OR c_val > 1) THEN
          result := 4;
        ELSIF (c_code = 5 OR c_code = 6) AND (c_val < 0 OR c_val > 100) THEN
          result := 4;
        ELSIF c_code = 7 AND (c_val < 200 OR c_val > 1000) THEN
          result := 4;
        ELSIF c_code = 10 AND (c_val < 1 OR c_val > 2) THEN
          result := 4;
        END_IF;
        (* 외부 요청: 시각 동기·만료·중복 *)
        IF result = 0 AND src = 2 THEN
          IF NOT time_ok THEN
            result := 10;
          ELSIF c_exp = 0 OR now_s > c_exp THEN
            result := 6;
          ELSE
            FOR k := 0 TO 7 DO
              IF c_hash <> 0 AND seen_hash[k] = c_hash THEN result := 7; END_IF;
            END_FOR;
          END_IF;
        END_IF;
        (* 모드·정비 모드(더 제한적인 쪽이 이긴다) *)
        IF result = 0 THEN
          IF mode = 0 THEN
            IF (src = 2) OR (NOT is_maint_on) THEN result := 1; END_IF;
          ELSIF maint THEN
            IF src = 2 THEN
              result := 2;
            ELSIF (NOT is_stop) AND (NOT is_maint_on) THEN
              result := 2;
            END_IF;
          ELSIF mode = 2 THEN
            IF (src = 1) AND (NOT op_mode_cmd) THEN result := 3; END_IF;
          ELSE
            IF src = 2 AND NOT c_acc THEN result := 3; END_IF;
          END_IF;
        END_IF;
        (* 비상정지·인터록·물리 타당성 *)
        IF (result = 0) AND estop AND start_or_change THEN
          result := 9;
        END_IF;
        IF result = 0 AND c_code = 1 AND c_val = 1 THEN
          IF interlock THEN
            result := 5;
          ELSIF lt101 > -1000.0 AND lt101 < 5.0 THEN
            result := 11;
          END_IF;
        END_IF;
        (* 수용: 반영 *)
        IF result = 0 THEN
          CASE c_code OF
            1: cmd_pump := (c_val = 1); fb_fault_pump := FALSE;
            2: cmd_agitator := (c_val = 1); fb_fault_agitator := FALSE;
            3: cmd_heater := (c_val = 1);
            4: cmd_cooler := (c_val = 1);
            5: sp_pump := INT_TO_REAL(c_val); hold_pump := 3000;
            6: sp_valve := INT_TO_REAL(c_val); hold_valve := 3000;
            7: sp_temp := INT_TO_REAL(c_val) / 10.0; hold_temp := 3000;
            10: mode := c_val;
            11: maint := TRUE; maint_op := INT_TO_WORD(c_val);
          END_CASE;
          IF src = 2 AND c_hash <> 0 THEN
            seen_hash[seen_idx] := c_hash;
            seen_idx := (seen_idx + 1) MOD 8;
          END_IF;
        END_IF;
        IF src = 1 THEN
          last_op_seq := op_seq; st_op_ack_code := INT_TO_WORD(result); st_op_ack_seq := op_seq;
        ELSE
          last_rq_seq := rq_seq; st_rq_ack_code := INT_TO_WORD(result); st_rq_ack_seq := rq_seq;
          st_rq_ack_hash_hi := rq_hash_hi; st_rq_ack_hash_lo := rq_hash_lo;
        END_IF;
      END_IF;
    END_FOR;

    (* ── 10. 생산 스케줄(설비 시각 기준, plant.yaml autopilot 과 같은 값) ── *)
    IF NOT ap_init AND pts > 0.0 THEN
      ap_next := pts; last_pts := pts; ap_init := TRUE;
      tgt_pump := sp_pump; tgt_valve := sp_valve; tgt_temp := sp_temp;
    END_IF;
    IF ap_init THEN
      IF pts >= ap_next THEN
        ap_next := pts + 86400.0;
        rnd := rnd * 1664525 + 1013904223;
        tgt_pump := 45.0 + (80.0 - 45.0) * DWORD_TO_REAL(SHR(rnd, 8)) / 16777216.0;
        rnd := rnd * 1664525 + 1013904223;
        tgt_valve := 35.0 + (60.0 - 35.0) * DWORD_TO_REAL(SHR(rnd, 8)) / 16777216.0;
        rnd := rnd * 1664525 + 1013904223;
        tgt_temp := 64.0 + (80.0 - 64.0) * DWORD_TO_REAL(SHR(rnd, 8)) / 16777216.0;
      END_IF;
      dpts := pts - last_pts;
      IF dpts < 0.0 OR dpts > 86400.0 THEN dpts := 0.0; END_IF;
      last_pts := pts;
      IF dpts > 0.0 THEN
        (* 가상설비 물리 적분과 같은 소구간(physics_max_substep_s) 복리 접근 *)
        ap_f := 1.0 - EXP(dpts / 5.0 * LN(1.0 - 5.0 / 7200.0));
        IF hold_pump <= 0 THEN sp_pump := sp_pump + (tgt_pump - sp_pump) * LREAL_TO_REAL(ap_f); END_IF;
        IF hold_valve <= 0 THEN sp_valve := sp_valve + (tgt_valve - sp_valve) * LREAL_TO_REAL(ap_f); END_IF;
        IF hold_temp <= 0 THEN sp_temp := sp_temp + (tgt_temp - sp_temp) * LREAL_TO_REAL(ap_f); END_IF;
      END_IF;
    END_IF;
    IF hold_pump > 0 THEN hold_pump := hold_pump - 1; END_IF;
    IF hold_valve > 0 THEN hold_valve := hold_valve - 1; END_IF;
    IF hold_temp > 0 THEN hold_temp := hold_temp - 1; END_IF;
  END_IF;

  (* ── 11. 출력: 인터록·비상정지는 명령과 상관없이 구동기를 막는다 ── *)
  q_pump := cmd_pump AND NOT interlock AND NOT estop;
  q_agitator := cmd_agitator AND NOT estop;
  q_heater := cmd_heater AND NOT estop;
  q_cooler := cmd_cooler AND NOT estop;
  q_sp_pump := INT_TO_WORD(REAL_TO_INT(sp_pump));
  q_sp_valve := INT_TO_WORD(REAL_TO_INT(sp_valve));
  q_sp_temp_x10 := INT_TO_WORD(REAL_TO_INT(sp_temp * 10.0));

  (* ── 12. 되읽기 감시: 기동 출력인데 전류가 오르지 않으면 정지(현장 통신이 정상일 때만) ── *)
  ton_fb_pump(IN := q_pump AND field_comm_ok AND it101 > -1000.0 AND it101 < 1.0, PT := T#5s);
  IF ton_fb_pump.Q THEN fb_fault_pump := TRUE; cmd_pump := FALSE; END_IF;
  ton_fb_agit(IN := q_agitator AND field_comm_ok AND it102 > -1000.0 AND it102 < 1.0, PT := T#5s);
  IF ton_fb_agit.Q THEN fb_fault_agitator := TRUE; cmd_agitator := FALSE; END_IF;

  (* ── 13. 상태 레지스터 ── *)
  heartbeat := heartbeat + 1;
  st_heartbeat := heartbeat;
  st_run := 1;
  st_mode := INT_TO_WORD(mode);
  st_maint := BOOL_TO_WORD(maint);
  st_maint_op := maint_op;
  st_interlock := BOOL_TO_WORD(interlock);
  st_field_comm := BOOL_TO_WORD(field_comm_ok);
  st_estop := BOOL_TO_WORD(estop);
  st_outputs := BOOL_TO_WORD(q_pump) OR SHL(BOOL_TO_WORD(q_agitator), 1)
                OR SHL(BOOL_TO_WORD(q_heater), 2) OR SHL(BOOL_TO_WORD(q_cooler), 3);
  st_fb_fault := BOOL_TO_WORD(fb_fault_pump) OR SHL(BOOL_TO_WORD(fb_fault_agitator), 1);
END_PROGRAM
