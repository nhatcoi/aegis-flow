#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* write_audit_log: cap phat, su dung va giai phong vung nho 64 byte (v0 - co loi) */
int write_audit_log(void) {
    char *data = (char *)malloc(64);
    if (data == NULL) return -1;
    memset(data, 0, 64);
    data[0] = 'A';
    return 0; /* thoat ma khong free */
}
