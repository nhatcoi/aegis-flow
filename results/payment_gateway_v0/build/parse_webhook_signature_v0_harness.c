#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int parse_webhook_signature(const char *);
int main(void) {
    char *payload = malloc(520 + 1);
    memset(payload, 'A', 520);
    payload[520] = '\0';
    int rc = parse_webhook_signature(payload);
    printf("rc=%d\n", rc);
    free(payload);
    return 0;
}
