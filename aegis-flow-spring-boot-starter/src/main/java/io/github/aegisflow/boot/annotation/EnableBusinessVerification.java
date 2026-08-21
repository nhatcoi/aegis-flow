package io.github.aegisflow.boot.annotation;

import io.github.aegisflow.boot.config.BusinessVerificationAutoConfiguration;
import org.springframework.context.annotation.Import;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Enables AegisFlow Business Workflow and Rules Verification in a Spring Boot application.
 */
@Documented
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Import(BusinessVerificationAutoConfiguration.class)
public @interface EnableBusinessVerification {

    /**
     * Base packages to scan for classes annotated with @BusinessWorkflow.
     * If empty, the package of the annotating class will be scanned.
     */
    String[] scanPackages() default {};
}
