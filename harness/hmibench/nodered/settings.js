// Node-RED 5 설정(hmibench). ① 기본 보안: 편집기 끔(흐름은 파일로만), HTTP 노드·대시보드는 Basic 인증 필수.
// 운전원 계정 operator / NR_OPERATOR_PW(환경변수). 인증 없는 명령·조회는 401.
const OP_USER = 'operator';
const OP_PW = process.env.NR_OPERATOR_PW || 'nr-operator-bench-pw';
function basicAuth(req, res, next) {
    const h = req.headers.authorization || '';
    const ok = h.startsWith('Basic ') && Buffer.from(h.slice(6), 'base64').toString() === `${OP_USER}:${OP_PW}`;
    if (ok) { req.benchUser = OP_USER; return next(); }
    res.set('WWW-Authenticate', 'Basic realm="hmibench"');
    res.status(401).send('auth required');
}
module.exports = {
    flowFile: 'flows.json',
    credentialSecret: false,
    uiPort: 1880,
    disableEditor: true,
    httpNodeMiddleware: basicAuth,          // /bench/* HTTP 끝점
    httpStaticAuth: undefined,
    dashboard: { middleware: [basicAuth] }, // Dashboard 2 화면(/dashboard)도 인증
    functionGlobalContext: {},
    logging: { console: { level: 'info', metrics: false, audit: false } },
};
