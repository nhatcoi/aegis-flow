#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* close_payment_session: cap phat, su dung va giai phong vung nho 16 byte (v0 - co loi) */
int close_payment_session(void) {
    char *data = (char *)malloc(16);
    if (data == NULL) return -1;
    memset(data, 0, 16);
    data[0] = 'A';
    free(data);
    free(data); /* giai phong lan thu hai */
    return 0;
}
