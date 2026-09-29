def refund_ratio(refund_amount, total_amount):
    if total_amount == 0:
        return 0
    return refund_amount // total_amount
