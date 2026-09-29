#include <limits.h>
#include <stdio.h>
int calculate_total_payment(int, int, int *);
int main(void) {
    int out = 0;
    int rc = calculate_total_payment(INT_MAX, 1, &out);
    printf("rc=%d out=%d\n", rc, out);
    return 0;
}
