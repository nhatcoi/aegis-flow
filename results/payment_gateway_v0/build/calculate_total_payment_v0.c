#include <limits.h>

/* calculate_total_payment: cong hai so nguyen 32-bit (v0 - co loi) */
int calculate_total_payment(int amount, int shipping_fee, int *out) {
    *out = amount + shipping_fee; /* co the tran so: undefined behavior */
    return 0;
}
