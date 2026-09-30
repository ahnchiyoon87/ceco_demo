// DMZ 요청 게이트웨이(Node-RED) 설정. 편집기는 열지 않는다(httpAdminRoot: false) — 흐름은 등록부 생성본만 쓴다.
const Ajv = require('/usr/src/node-red/node_modules/ajv');

module.exports = {
    flowFile: 'flows.json',
    credentialSecret: false,              // 자격 증명은 ${환경변수} 로만 둔다(파일에 비밀값 없음)
    uiPort: 8088,
    httpAdminRoot: false,
    mqttReconnectTime: 1000,              // 브로커가 돌아오면 1초 안에 다시 붙는다(기본 15초)
    functionGlobalContext: {
        crypto: require('crypto'),
        registry: require('/opt/ar100/registry/tags.json'),
        allow: require('/opt/ar100/registry/work_masters.allow.json'),
        validateJob: new Ajv({ strict: false, allErrors: false })
            .compile(require('/opt/ar100/registry/schemas/job_request.schema.json')),
    },
    logging: { console: { level: 'info', metrics: false, audit: false } },
    diagnostics: { enabled: false },
    runtimeState: { enabled: false },
    telemetry: { enabled: false },
    externalModules: { autoInstall: false, palette: { allowInstall: false } },
};
