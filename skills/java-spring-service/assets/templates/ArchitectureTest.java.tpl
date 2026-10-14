package {{package}};

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noFields;
import static com.tngtech.archunit.library.dependencies.SlicesRuleDefinition.slices;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import jakarta.persistence.Entity;

@AnalyzeClasses(packages = "{{package}}", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {

    @ArchTest
    static final ArchRule controllers_do_not_touch_repositories = noClasses().that().resideInAPackage("..api..")
        .should().dependOnClassesThat().resideInAPackage("..repository..");

    @ArchTest
    static final ArchRule api_never_exposes_entities = noClasses().that().resideInAPackage("..api..")
        .should().dependOnClassesThat().areAnnotatedWith(Entity.class);

    @ArchTest
    static final ArchRule no_field_injection = noFields()
        .should().beAnnotatedWith(org.springframework.beans.factory.annotation.Autowired.class);

    @ArchTest
    static final ArchRule no_package_cycles = slices().matching("{{package}}.(*)..").should().beFreeOfCycles();
}
