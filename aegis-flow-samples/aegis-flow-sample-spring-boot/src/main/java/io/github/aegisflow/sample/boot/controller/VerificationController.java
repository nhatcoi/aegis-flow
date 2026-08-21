package io.github.aegisflow.sample.boot.controller;

import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.sample.boot.model.VerificationReportDto;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * REST controller providing access to AegisFlow Verification Reports.
 */
@RestController
@RequestMapping("/api/verification")
public class VerificationController {

    private final VerificationService verificationService;

    public VerificationController(VerificationService verificationService) {
        this.verificationService = verificationService;
    }

    /**
     * Gets all verification reports for the registered business workflows.
     */
    @GetMapping("/reports")
    public ResponseEntity<List<VerificationReportDto>> getAllReports() {
        List<VerificationReportDto> dtos = verificationService.getReports().values().stream()
                .map(VerificationReportDto::from)
                .toList();
        return ResponseEntity.ok(dtos);
    }

    /**
     * Manually triggers a re-verification of all business workflows.
     */
    @PostMapping("/run")
    public ResponseEntity<Map<String, Object>> triggerReverification() {
        var reports = verificationService.verifyAll();
        return ResponseEntity.ok(Map.of(
                "totalWorkflows", reports.size(),
                "hasErrors", verificationService.hasErrors(),
                "timestamp", System.currentTimeMillis()
        ));
    }
}
