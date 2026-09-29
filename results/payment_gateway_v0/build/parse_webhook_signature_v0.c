#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* parse_webhook_signature: sao chep du lieu dau vao vao bo dem 65 byte (v0 - co loi) */
int parse_webhook_signature(const char *raw_signature) {
    char buffer[65];
    strcpy(buffer, raw_signature); /* khong kiem tra kich thuoc dich */
    printf("%s\n", buffer);
    return 0;
}
