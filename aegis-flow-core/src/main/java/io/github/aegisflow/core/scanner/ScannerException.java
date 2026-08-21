package io.github.aegisflow.core.scanner;

/**
 * Exception thrown when scanning or extracting a workflow model fails.
 */
public class ScannerException extends RuntimeException {

    public ScannerException(String message) {
        super(message);
    }

    public ScannerException(String message, Throwable cause) {
        super(message, cause);
    }
}
