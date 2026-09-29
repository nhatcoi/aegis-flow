# Bảng tổng hợp trước/sau

| CWE | Vị trí | Trạng thái v0 | Trạng thái v1 | Công cụ xác minh |
|---|---|---|---|---|
| CWE-190 | order_total_counter | Z3 SAT: {'amount': 2147483647, 'shipping_fee': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2143221476 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | daily_transaction_counter | Z3 SAT: {'tx_today': 2147483647, 'tx_backlog': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2145383168 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | active_session_counter | Z3 SAT: {'active_sessions': 2147483647, 'pending_sessions': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2130435216 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | refund_total_vnd | Z3 SAT: {'refunded_vnd': 2147483647, 'pending_refund_vnd': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2112845824 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | webhook_retry_counter | Z3 SAT: {'retries_today': 2147483647, 'retries_backlog': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2147203978 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | settlement_batch_bytes | Z3 SAT: {'batch_bytes': 2147483647, 'header_bytes': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2137979759 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
