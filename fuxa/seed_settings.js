// FUXA 사용자 설정(_appdata/mysettings.json)에 '없는 값만' 채운다(기동 때마다, 멱등). 강사가 편집기에서 바꾼 값은 덮지 않는다.
//   - 보안(로그인) 켜기: 화면 값 보기는 guest, 운전원 명령은 로그인 사용자, 프로젝트·설정 변경은 관리자만(FUXA 1.3.4 규칙)
//   - JWT 비밀: 환경변수 FUXA_JWT_SECRET(저장소에 두지 않는다). 없으면 FUXA 가 기동마다 새로 만들어 로그인이 풀린다
//   - DAQ(OT 이력) 보존 7일: 설정 API 로 넣으면 프로젝트 넣기와 함께 런타임이 1초 안에 두 번 재시작돼 DAQ 파일이 지워진다
const fs = require('fs');
const file = '_appdata/mysettings.json';
const seed = JSON.parse(fs.readFileSync('/seed/mysettings.json', 'utf8'));
const cur = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
const added = [];
for (const [k, v] of Object.entries(seed)) if (!(k in cur)) { cur[k] = v; added.push(k); }
if (!cur.secretCode && process.env.FUXA_JWT_SECRET) { cur.secretCode = process.env.FUXA_JWT_SECRET; added.push('secretCode'); }
if (added.length) {
  fs.mkdirSync('_appdata', { recursive: true });
  fs.writeFileSync(file, JSON.stringify(cur, null, 4), { mode: 0o600 });
}
console.log(`[fuxa-seed] 사용자 설정: ${added.length ? '채움 ' + added.join(', ') : '그대로'}`);
