package com.getjobs;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import lombok.extern.slf4j.Slf4j;
import java.io.FileWriter;

@Slf4j
@Component
public class StartupRunner implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) throws Exception {
        String msg = "===========================================\n" +
                      "Application startup COMPLETED successfully!\n" +
                      "Time: " + java.time.LocalDateTime.now() + "\n" +
                      "Server is running on port 8888\n" +
                      "===========================================\n";
        log.info(msg);

        try (FileWriter fw = new FileWriter("target/startup_ok.txt")) {
            fw.write(msg);
        } catch (Exception e) {
            log.warn("Could not write startup file: {}", e.getMessage());
        }
    }
}
