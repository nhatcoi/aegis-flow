package io.github.aegisflow.boot.runner;

import io.github.aegisflow.boot.config.AegisFlowProperties;
import io.github.aegisflow.boot.service.VerificationService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;

import java.util.Objects;

/**
 * Spring Boot ApplicationRunner executing workflow verification upon startup.
 */
public class BusinessVerificationRunner implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(BusinessVerificationRunner.class);

    private final VerificationService verificationService;
    private final AegisFlowProperties properties;

    public BusinessVerificationRunner(VerificationService verificationService, AegisFlowProperties properties) {
        this.verificationService = Objects.requireNonNull(verificationService, "verificationService cannot be null");
        this.properties = Objects.requireNonNull(properties, "properties cannot be null");
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!properties.isEnabled()) {
            log.info("AegisFlow Business Workflow Verification is disabled by configuration");
            return;
        }

        log.info("Starting automated AegisFlow Business Workflow Verification...");
        verificationService.verifyAll();

        if (properties.isFailOnError() && verificationService.hasErrors()) {
            String msg = "AegisFlow Verification failed with critical errors and 'aegisflow.verification.fail-on-error' is set to true";
            log.error(msg);
            throw new IllegalStateException(msg);
        }
    }
}
