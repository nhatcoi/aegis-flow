#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* parse_order_id: sao chep du lieu dau vao vao bo dem 21 byte (v1 - da va) */
int parse_order_id(const char *raw_order_id) {
    char buffer[21];
    if (raw_order_id == NULL) return -1;
    size_t len = strnlen(raw_order_id, sizeof buffer);
    if (len >= sizeof buffer) return -1; /* tu choi input qua dai thay vi cat bot */
    memcpy(buffer, raw_order_id, len);
    buffer[len] = '\0';
    printf("%s\n", buffer);
    return 0;
}
