package io.github.aegisflow.core.report;

import java.util.Objects;

/**
 * Diagnostic finding produced by a verification engine.
 */
public class Diagnostic {

    public enum Severity {
        ERROR,
        WARNING,
        INFO
    }

    private final Severity severity;
    private final String engineName;
    private final String ruleId;
    private final String message;
    private final String location;

    public Diagnostic(Severity severity, String engineName, String ruleId, String message, String location) {
        this.severity = Objects.requireNonNull(severity, "severity cannot be null");
        this.engineName = engineName != null ? engineName : "UNKNOWN";
        this.ruleId = ruleId != null ? ruleId : "";
        this.message = Objects.requireNonNull(message, "message cannot be null");
        this.location = location != null ? location : "";
    }

    public Severity getSeverity() {
        return severity;
    }

    public String getEngineName() {
        return engineName;
    }

    public String getRuleId() {
        return ruleId;
    }

    public String getMessage() {
        return message;
    }

    public String getLocation() {
        return location;
    }

    @Override
    public String toString() {
        String prefix = "[" + severity + "][" + engineName + "]";
        String r = ruleId.isEmpty() ? "" : "[" + ruleId + "]";
        String loc = location.isEmpty() ? "" : " at " + location;
        return prefix + r + " " + message + loc;
    }
}
