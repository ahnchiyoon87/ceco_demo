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
