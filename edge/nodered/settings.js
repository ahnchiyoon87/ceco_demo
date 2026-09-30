// Node-RED 엣지 설정. 계정·비밀번호는 환경변수(.env)에서 받는다.
const bcrypt = require('/usr/src/node-red/node_modules/bcryptjs');
const registry = require('/opt/ar100/registry/tags.json');

module.exports = {
    flowFile: 'flows.json',
    credentialSecret: false,              // 자격 증명은 ${환경변수} 로만 둔다(파일에 비밀값 없음)
    uiPort: 1880,
    mqttReconnectTime: 1000,              // 브로커가 돌아오면 1초 안에 다시 붙는다(기본 15초)
    adminAuth: {
        type: 'credentials',
        users: [{
            username: process.env.EDGE_ADMIN_USER,
            password: bcrypt.hashSync(process.env.EDGE_ADMIN_PASSWORD, 8),
            permissions: '*',
        }],
    },
    // 흐름이 쓰는 공용 값: 등록부 생성본(신호·명령·레지스터 지도·작업 정의 표·요청 스키마)
    functionGlobalContext: {
        crypto: require('crypto'),
        registry,
        workMastersOt: require('/opt/ar100/registry/work_masters.ot.json'),
        jobSchema: require('/opt/ar100/registry/schemas/job_request.schema.json'),
    },
    // 끊김 버퍼는 디스크 컨텍스트에 둔다(엣지 재시작에도 남음). 나머지는 메모리.
    contextStorage: {
        default: { module: 'memory' },
        disk: { module: 'localfilesystem', config: { flushInterval: 5 } },
    },
    logging: { console: { level: 'info', metrics: false, audit: false } },
    editorTheme: { projects: { enabled: false }, tours: false },
    diagnostics: { enabled: false },
    runtimeState: { enabled: false },
    telemetry: { enabled: false },
    externalModules: { autoInstall: false, palette: { allowInstall: false } },
};
