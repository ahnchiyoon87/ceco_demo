package exp;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.flink.table.api.EnvironmentSettings;
import org.apache.flink.table.api.StatementSet;
import org.apache.flink.table.api.TableEnvironment;

/**
 * Flink HA-B(ZooKeeper HA + 애플리케이션 모드)용 SQL 실행기 — 연결 코드.
 * 공식 flink-kubernetes-operator 의 "flink-sql-runner-example" 과 같은 역할: SQL 파일을 읽어 TableEnvironment 로 실행한다.
 * HA 애플리케이션 모드는 잡 하나만 허용하므로 INSERT 문을 모두 한 StatementSet(잡 1개)으로 묶는다.
 * SQL 본문(V1 01~04)은 바꾸지 않는다. SET 'k' = 'v' 는 설정으로, 나머지(CREATE 등)는 executeSql 로.
 *   standalone-job --job-classname exp.SqlRunner /opt/flink/sql/app.sql
 */
public class SqlRunner {
    static final Pattern SET = Pattern.compile("(?is)^SET\\s+'([^']+)'\\s*=\\s*'([^']*)'$");

    public static void main(String[] args) throws Exception {
        String script = Files.readString(Path.of(args[0]), StandardCharsets.UTF_8);
        TableEnvironment t = TableEnvironment.create(EnvironmentSettings.inStreamingMode());
        StatementSet inserts = t.createStatementSet();
        int n = 0;
        for (String stmt : split(script)) {
            Matcher m = SET.matcher(stmt);
            if (m.matches()) {
                if (!m.group(1).equals("pipeline.name")) t.getConfig().getConfiguration().setString(m.group(1), m.group(2));
            } else if (stmt.regionMatches(true, 0, "INSERT", 0, 6)) {
                inserts.addInsertSql(stmt);
                n++;
            } else {
                t.executeSql(stmt);
            }
        }
        t.getConfig().getConfiguration().setString("pipeline.name", "AR100-Tier1-HAB(" + n + " INSERT)");
        inserts.execute();
    }

    /** '--' 줄 주석을 지우고, 문자열 밖의 ';' 로 문장을 나눈다. */
    public static List<String> split(String script) {
        StringBuilder clean = new StringBuilder();
        for (String line : script.split("\n")) {
            String l = line;
            boolean inStr = false;
            for (int i = 0; i < l.length() - 1; i++) {
                char c = l.charAt(i);
                if (c == '\'') inStr = !inStr;
                if (!inStr && c == '-' && l.charAt(i + 1) == '-') { l = l.substring(0, i); break; }
            }
            clean.append(l).append('\n');
        }
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean inStr = false;
        for (char c : clean.toString().toCharArray()) {
            if (c == '\'') inStr = !inStr;
            if (c == ';' && !inStr) {
                if (!cur.toString().isBlank()) out.add(cur.toString().trim());
                cur.setLength(0);
            } else {
                cur.append(c);
            }
        }
        if (!cur.toString().isBlank()) out.add(cur.toString().trim());
        return out;
    }
}
