package io.github.aegisflow.core.spi;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Context and configuration passed to verification engines.
 */
public class VerificationContext {

    private final Map<String, Object> properties;

    public VerificationContext() {
        this(Collections.emptyMap());
    }

    public VerificationContext(Map<String, Object> properties) {
        this.properties = properties != null ? new LinkedHashMap<>(properties) : new LinkedHashMap<>();
    }

    public void setProperty(String key, Object value) {
        properties.put(key, value);
    }

    public Optional<Object> getProperty(String key) {
        return Optional.ofNullable(properties.get(key));
    }

    public <T> T getProperty(String key, Class<T> type, T defaultValue) {
        Object val = properties.get(key);
        if (val != null && type.isInstance(val)) {
            return type.cast(val);
        }
        return defaultValue;
    }

    public Map<String, Object> getAllProperties() {
        return Collections.unmodifiableMap(properties);
    }
}
