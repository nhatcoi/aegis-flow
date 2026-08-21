package io.github.aegisflow.boot.service;

import io.github.aegisflow.boot.config.AegisFlowProperties;
import io.github.aegisflow.core.annotation.BusinessWorkflow;
import io.github.aegisflow.core.pipeline.VerificationPipeline;
import io.github.aegisflow.core.report.VerificationReport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.config.BeanDefinition;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.ClassPathScanningCandidateComponentProvider;
import org.springframework.core.type.filter.AnnotationTypeFilter;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Service responsible for scanning, verifying, and storing verification reports in Spring Boot.
 */
public class VerificationService {

    private static final Logger log = LoggerFactory.getLogger(VerificationService.class);

    private final VerificationPipeline pipeline;
    private final ApplicationContext applicationContext;
    private final AegisFlowProperties properties;

    private final Map<String, VerificationReport> reportMap = new ConcurrentHashMap<>();

    public VerificationService(VerificationPipeline pipeline, ApplicationContext applicationContext, AegisFlowProperties properties) {
        this.pipeline = Objects.requireNonNull(pipeline, "pipeline cannot be null");
        this.applicationContext = Objects.requireNonNull(applicationContext, "applicationContext cannot be null");
        this.properties = Objects.requireNonNull(properties, "properties cannot be null");
    }

    /**
     * Executes verification for all detected @BusinessWorkflow classes.
     *
     * @return map of workflow name to VerificationReport
     */
    public Map<String, VerificationReport> verifyAll() {
        Set<Class<?>> workflowClasses = discoverWorkflowClasses();
        log.info("Found {} @BusinessWorkflow classes for verification", workflowClasses.size());

        for (Class<?> clazz : workflowClasses) {
            try {
                VerificationReport report = pipeline.verifyClass(clazz);
                reportMap.put(report.getWorkflowName(), report);
                System.out.println(report.toPrettyString());
            } catch (Exception ex) {
                log.error("Failed to verify workflow class: {}", clazz.getName(), ex);
            }
        }

        return getReports();
    }

    private Set<Class<?>> discoverWorkflowClasses() {
        Set<Class<?>> result = new LinkedHashSet<>();

        // 1. Discover from Spring Beans in ApplicationContext
        Map<String, Object> annotatedBeans = applicationContext.getBeansWithAnnotation(BusinessWorkflow.class);
        for (Object bean : annotatedBeans.values()) {
            result.add(bean.getClass());
        }

        // 2. Discover from packages using ClassPathScanningCandidateComponentProvider
        List<String> packagesToScan = new ArrayList<>(properties.getScanPackages());
        if (packagesToScan.isEmpty()) {
            // Default to package of main application class or root beans
            for (String beanName : applicationContext.getBeanDefinitionNames()) {
                Object bean = applicationContext.getBean(beanName);
                if (bean.getClass().isAnnotationPresent(org.springframework.boot.autoconfigure.SpringBootApplication.class)) {
                    packagesToScan.add(bean.getClass().getPackageName());
                    break;
                }
            }
        }

        if (packagesToScan.isEmpty() && applicationContext.getParent() == null) {
            packagesToScan.add(""); // scan entire classpath if nothing specified
        }

        ClassPathScanningCandidateComponentProvider scanner = new ClassPathScanningCandidateComponentProvider(false);
        scanner.addIncludeFilter(new AnnotationTypeFilter(BusinessWorkflow.class));

        for (String pkg : packagesToScan) {
            for (BeanDefinition bd : scanner.findCandidateComponents(pkg)) {
                try {
                    Class<?> clazz = Class.forName(bd.getBeanClassName());
                    result.add(clazz);
                } catch (ClassNotFoundException e) {
                    log.warn("Could not load class for verification: {}", bd.getBeanClassName());
                }
            }
        }

        return result;
    }

    public Map<String, VerificationReport> getReports() {
        return Collections.unmodifiableMap(reportMap);
    }

    public Optional<VerificationReport> getReport(String workflowName) {
        return Optional.ofNullable(reportMap.get(workflowName));
    }

    public boolean hasErrors() {
        return reportMap.values().stream().anyMatch(VerificationReport::hasErrors);
    }
}
