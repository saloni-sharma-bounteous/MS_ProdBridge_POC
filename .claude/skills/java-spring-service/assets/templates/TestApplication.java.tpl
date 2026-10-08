package {{package}};

import org.springframework.boot.SpringApplication;

/** Run this class (or `mvn spring-boot:test-run`) to start the service against a throw-away database. */
public class TestApplication {

    public static void main(String[] args) {
        SpringApplication.from({{app_class}}::main).with(TestcontainersConfiguration.class).run(args);
    }
}
