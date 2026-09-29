#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* parse_webhook_signature: sao chep du lieu dau vao vao bo dem 65 byte (v1 - da va) */
int parse_webhook_signature(const char *raw_signature) {
    char buffer[65];
    if (raw_signature == NULL) return -1;
    size_t len = strnlen(raw_signature, sizeof buffer);
    if (len >= sizeof buffer) return -1; /* tu choi input qua dai thay vi cat bot */
    memcpy(buffer, raw_signature, len);
    buffer[len] = '\0';
    printf("%s\n", buffer);
    return 0;
}
