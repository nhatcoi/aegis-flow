#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* release_card_token_buffer: cap phat, su dung va giai phong vung nho 33 byte (v0 - co loi) */
int release_card_token_buffer(void) {
    char *data = (char *)malloc(33);
    if (data == NULL) return -1;
    memset(data, 0, 33);
    free(data);
    data[0] = 'A'; /* ghi sau khi da free */
    return 0;
}
