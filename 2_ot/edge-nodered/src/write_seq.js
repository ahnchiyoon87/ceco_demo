// 앞의 쓰기(명령 코드·값)가 끝났으니 순번을 쓴다.
if (!msg.seqWrite) return null;
return { payload: msg.seqWrite };
