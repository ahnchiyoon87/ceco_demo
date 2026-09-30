PROGRAM main
  VAR
    raw0 AT %IW0 : WORD;
    out0 AT %QW0 : WORD;
    cnt AT %QW1 : WORD;
    sp AT %QW100 : WORD;
  END_VAR

  out0 := raw0;
    cnt := cnt + 1;
    sp := 61;
END_PROGRAM


CONFIGURATION Config0

  RESOURCE Res0 ON PLC
    TASK task0(INTERVAL := T#100ms,PRIORITY := 1);
    PROGRAM instance0 WITH task0 : main;
  END_RESOURCE
END_CONFIGURATION
