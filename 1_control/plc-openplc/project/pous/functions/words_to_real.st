(* 레지스터 2워드(big-endian ABCD) → IEEE 754 REAL. 가상설비·PLC 가 float32 를 워드 둘로 싣는다. *)
FUNCTION WORDS_TO_REAL : REAL
  VAR_INPUT
    hi : WORD;
    lo : WORD;
  END_VAR
  VAR
    bits : DWORD;
    e : DINT;
    m : DINT;
    v : REAL;
  END_VAR
  bits := SHL(WORD_TO_DWORD(hi), 16) OR WORD_TO_DWORD(lo);
  e := DWORD_TO_DINT(SHR(bits, 23) AND 16#FF);
  m := DWORD_TO_DINT(bits AND 16#7FFFFF);
  IF e = 0 THEN
    v := 0.0;
  ELSIF e = 255 THEN
    v := -1.0E30;   (* NaN·무한대는 결측으로 본다 *)
  ELSE
    v := (1.0 + DINT_TO_REAL(m) / 8388608.0) * EXPT(2.0, DINT_TO_REAL(e - 127));
  END_IF;
  IF (bits AND 16#80000000) <> 0 THEN
    v := -v;
  END_IF;
  WORDS_TO_REAL := v;
END_FUNCTION
