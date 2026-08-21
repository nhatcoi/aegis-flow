package io.github.aegisflow.sample.boot;

import io.github.aegisflow.boot.annotation.EnableBusinessVerification;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Sample Spring Boot Application applying the AegisFlow.
 */
@SpringBootApplication
@EnableBusinessVerification(scanPackages = {"io.github.aegisflow.sample.boot.workflow"})
public class SampleApplication {

    public static void main(String[] args) {
        SpringApplication.run(SampleApplication.class, args);
    }
}
