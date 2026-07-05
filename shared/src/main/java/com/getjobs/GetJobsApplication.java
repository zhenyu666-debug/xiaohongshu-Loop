package com.getjobs;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ApplicationContext;
import org.springframework.scheduling.annotation.EnableScheduling;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

@SpringBootApplication
@EnableScheduling
public class GetJobsApplication {

    private static ApplicationContext applicationContext;

    public static void main(String[] args) {
        try {
            applicationContext = SpringApplication.run(GetJobsApplication.class, args);
            // 启动后,自动给所有需要 IDENTITY 的表添加 autoincrement 列属性
            try {
                fixSqliteAutoIncrement();
            } catch (Exception e) {
                System.err.println("[SchemaFix] " + e.getMessage());
            }
            System.out.println("===========================================");
            System.out.println("Application started successfully!");
            System.out.println("Server running on port 8888");
            System.out.println("===========================================");
        } catch (Throwable t) {
            System.err.println("===========================================");
            System.err.println("APPLICATION STARTUP FAILED:");
            t.printStackTrace(System.err);
            System.err.println("===========================================");
            System.exit(1);
        }
    }

    /**
     * 给 SQLite 表的 id 列添加自增属性。
     * SQLite 不支持 ALTER TABLE 改主键,所以策略是:
     * 1. 检查目标表是否存在
     * 2. 检查 id 列的 PK 类型 (INTEGER PRIMARY KEY 才会自增)
     * 3. 如果不是 INTEGER PRIMARY KEY,用 SQLITE 的方法: rename -> create new -> copy data
     */
    private static void fixSqliteAutoIncrement() throws Exception {
        // 表名 -> entity 中 @Id 字段名
        String[][] tables = {
                {"cookie", "id"},
                {"zhilian_config", "id"},
                {"zhilian_data", "id"},
                {"zhilian_option", "id"},
                {"liepin_config", "id"},
                {"task_session", "id"},
        };
        var ds = applicationContext.getBean(DataSource.class);
        try (Connection conn = ds.getConnection(); Statement st = conn.createStatement()) {
            for (String[] t : tables) {
                String table = t[0];
                String idCol = t[1];
                // 检查表是否存在
                try (ResultSet rs = st.executeQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='" + table + "'")) {
                    if (!rs.next()) continue;
                }
                // 拿 DDL
                String ddl = null;
                try (ResultSet rs = st.executeQuery("SELECT sql FROM sqlite_master WHERE type='table' AND name='" + table + "'")) {
                    if (rs.next()) ddl = rs.getString(1);
                }
                if (ddl == null) continue;
                // 已经 INTEGER PRIMARY KEY,跳过 (兼容带引号或不带引号)
                String upper = ddl.toUpperCase();
                if (upper.contains("\"" + idCol.toUpperCase() + "\" INTEGER PRIMARY KEY")
                        || upper.contains(idCol.toUpperCase() + " INTEGER PRIMARY KEY")) {
                    System.out.println("[SchemaFix] " + table + " 已经 INTEGER PRIMARY KEY,跳过");
                    continue;
                }
                // 通过 PRAGMA table_info 拿所有列名
                java.util.List<String> colDefs = new java.util.ArrayList<>();
                try (ResultSet rs = st.executeQuery("PRAGMA table_info(" + table + ")")) {
                    while (rs.next()) {
                        colDefs.add("\"" + rs.getString("name") + "\" " + rs.getString("type"));
                    }
                }
                if (colDefs.isEmpty()) continue;
                // 重建表
                String tempName = table + "_old_" + System.currentTimeMillis();
                st.execute("ALTER TABLE " + table + " RENAME TO " + tempName);
                StringBuilder newDdl = new StringBuilder("CREATE TABLE " + table + " (");
                boolean first = true;
                for (int i = 0; i < colDefs.size(); i++) {
                    String col = colDefs.get(i);
                    if (!first) newDdl.append(", ");
                    if (i == 0) {
                        // 第一列视为 id,改成 INTEGER PRIMARY KEY AUTOINCREMENT
                        newDdl.append("\"").append(idCol).append("\" INTEGER PRIMARY KEY AUTOINCREMENT");
                    } else {
                        newDdl.append(col);
                    }
                    first = false;
                }
                newDdl.append(")");
                st.execute(newDdl.toString());
                st.execute("INSERT INTO " + table + " SELECT * FROM " + tempName);
                st.execute("DROP TABLE " + tempName);
                System.out.println("[SchemaFix] " + table + " 重建完成,id 改为 INTEGER PRIMARY KEY AUTOINCREMENT");
            }
        }
    }

    public static ApplicationContext getApplicationContext() {
        return applicationContext;
    }
}
