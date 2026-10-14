package {{package}};

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;

@SpringBootTest(properties = "spring.security.oauth2.resourceserver.jwt.issuer-uri=http://issuer.test/")
@Import(TestcontainersConfiguration.class)
class ApplicationTests {

    @Test
    void contextLoadsAndMigrationsApply() {
        // Starting the context runs the Flyway migrations and validates the JPA mapping against them.
    }
}
