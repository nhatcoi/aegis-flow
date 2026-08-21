package io.github.aegisflow.boot.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.ArrayList;
import java.util.List;

/**
 * Configuration properties for AegisFlow Business Verification.
 */
@ConfigurationProperties(prefix = "aegisflow.verification")
public class AegisFlowProperties {

    /**
     * Whether business workflow verification is enabled.
     */
    private boolean enabled = true;

    /**
     * Whether application startup should fail if any verification error is detected.
     */
    private boolean failOnError = false;

    /**
     * Packages to scan for @BusinessWorkflow definitions.
     */
    private List<String> scanPackages = new ArrayList<>();

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public boolean isFailOnError() {
        return failOnError;
    }

    public void setFailOnError(boolean failOnError) {
        this.failOnError = failOnError;
    }

    public List<String> getScanPackages() {
        return scanPackages;
    }

    public void setScanPackages(List<String> scanPackages) {
        this.scanPackages = scanPackages;
    }
}
