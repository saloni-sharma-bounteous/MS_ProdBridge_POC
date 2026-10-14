package {{package}};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {{app_class}} {

    public static void main(String[] args) {
        SpringApplication.run({{app_class}}.class, args);
    }
}
