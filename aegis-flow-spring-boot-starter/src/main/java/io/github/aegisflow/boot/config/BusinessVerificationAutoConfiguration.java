package io.github.aegisflow.boot.config;

import io.github.aegisflow.boot.runner.BusinessVerificationRunner;
import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.scanner.WorkflowScanner;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;

/**
 * Auto-configuration for AegisFlow in Spring Boot.
 */
@AutoConfiguration
@EnableConfigurationProperties(AegisFlowProperties.class)
@ConditionalOnProperty(prefix = "aegisflow.verification", name = "enabled", havingValue = "true", matchIfMissing = true)
public class BusinessVerificationAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public WorkflowScanner workflowScanner() {
        return new WorkflowScanner();
    }

    @Bean
    @ConditionalOnMissingBean
    public VerificationPipeline verificationPipeline(WorkflowScanner workflowScanner) {
        VerificationPipeline pipeline = new VerificationPipeline(workflowScanner);
        pipeline.discoverEngines();
        return pipeline;
    }

    @Bean
    @ConditionalOnMissingBean
    public VerificationService verificationService(VerificationPipeline verificationPipeline,
                                                   ApplicationContext applicationContext,
                                                   AegisFlowProperties aegisFlowProperties) {
        return new VerificationService(verificationPipeline, applicationContext, aegisFlowProperties);
    }

    @Bean
    @ConditionalOnMissingBean
    public BusinessVerificationRunner businessVerificationRunner(VerificationService verificationService,
                                                                 AegisFlowProperties aegisFlowProperties) {
        return new BusinessVerificationRunner(verificationService, aegisFlowProperties);
    }
}
