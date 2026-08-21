package io.github.aegisflow.sample.boot.model;

import io.github.aegisflow.core.report.VerificationReport;

import java.util.List;
import java.util.Map;

/**
 * Data Transfer Object for Verification Report API.
 */
public class VerificationReportDto {

    private String workflowName;
    private String status;
    private long durationMs;
    private int diagnosticCount;
    private int counterExampleCount;
    private List<String> diagnostics;

    public static VerificationReportDto from(VerificationReport report) {
        VerificationReportDto dto = new VerificationReportDto();
        dto.workflowName = report.getWorkflowName();
        dto.status = report.getStatus().name();
        dto.durationMs = report.getTotalDurationMs();
        dto.diagnosticCount = report.getDiagnostics().size();
        dto.counterExampleCount = report.getCounterExamples().size();
        dto.diagnostics = report.getDiagnostics().stream()
                .map(d -> "[" + d.getSeverity() + "] " + d.getMessage())
                .toList();
        return dto;
    }

    public String getWorkflowName() {
        return workflowName;
    }

    public String getStatus() {
        return status;
    }

    public long getDurationMs() {
        return durationMs;
    }

    public int getDiagnosticCount() {
        return diagnosticCount;
    }

    public int getCounterExampleCount() {
        return counterExampleCount;
    }

    public List<String> getDiagnostics() {
        return diagnostics;
    }
}
