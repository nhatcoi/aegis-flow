package io.github.aegisflow.core.expr;

/**
 * Exception thrown when parsing a DSL or constraint expression fails.
 */
public class ParseException extends RuntimeException {

    public ParseException(String message) {
        super(message);
    }

    public ParseException(String message, Throwable cause) {
        super(message, cause);
    }
}
