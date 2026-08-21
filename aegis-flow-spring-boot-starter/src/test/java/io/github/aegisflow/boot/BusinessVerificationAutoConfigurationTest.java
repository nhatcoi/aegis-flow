package io.github.aegisflow.boot;

import io.github.aegisflow.boot.config.BusinessVerificationAutoConfiguration;
import io.github.aegisflow.boot.runner.BusinessVerificationRunner;
import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

import static org.assertj.core.api.Assertions.assertThat;

class BusinessVerificationAutoConfigurationTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(BusinessVerificationAutoConfiguration.class));

    @Test
    void testAutoConfigurationEnabledByDefault() {
        contextRunner.run(context -> {
            assertThat(context).hasSingleBean(VerificationPipeline.class);
            assertThat(context).hasSingleBean(VerificationService.class);
            assertThat(context).hasSingleBean(BusinessVerificationRunner.class);
        });
    }

    @Test
    void testAutoConfigurationCanBeDisabled() {
        contextRunner.withPropertyValues("aegisflow.verification.enabled=false")
                .run(context -> {
                    assertThat(context).doesNotHaveBean(VerificationPipeline.class);
                    assertThat(context).doesNotHaveBean(VerificationService.class);
                });
    }
}
