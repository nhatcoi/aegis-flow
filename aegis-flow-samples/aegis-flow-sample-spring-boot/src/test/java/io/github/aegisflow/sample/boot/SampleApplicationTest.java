package io.github.aegisflow.sample.boot;

import io.github.aegisflow.boot.service.VerificationService;
import io.github.aegisflow.core.report.VerificationReport;
import io.github.aegisflow.core.report.VerificationStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class SampleApplicationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private VerificationService verificationService;

    @Autowired
    private TestRestTemplate restTemplate;

    @Test
    void contextLoadsAndWorkflowsAreVerifiedOnStartup() {
        assertThat(verificationService).isNotNull();

        Map<String, VerificationReport> reports = verificationService.getReports();
        assertThat(reports)
                .containsKey("OrderProcessingWorkflow")
                .containsKey("PaymentTransactionWorkflow");

        VerificationReport orderReport = reports.get("OrderProcessingWorkflow");
        assertThat(orderReport.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(orderReport.hasErrors()).isFalse();

        VerificationReport paymentReport = reports.get("PaymentTransactionWorkflow");
        assertThat(paymentReport.getStatus()).isEqualTo(VerificationStatus.PASSED);
        assertThat(paymentReport.hasErrors()).isFalse();
    }

    @Test
    void testVerificationReportsEndpoint() {
        String url = "http://localhost:" + port + "/api/verification/reports";
        ResponseEntity<Object[]> response = restTemplate.getForEntity(url, Object[].class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody()).hasSize(2);
    }
}
