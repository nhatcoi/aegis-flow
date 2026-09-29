#include <limits.h>

/* calculate_total_payment: cong hai so nguyen 32-bit (v1 - da va) */
int calculate_total_payment(int amount, int shipping_fee, int *out) {
    if ((shipping_fee > 0 && amount > INT_MAX - shipping_fee) || (shipping_fee < 0 && amount < INT_MIN - shipping_fee)) {
        return -1; /* tu choi thay vi de tran so */
    }
    *out = amount + shipping_fee;
    return 0;
}
