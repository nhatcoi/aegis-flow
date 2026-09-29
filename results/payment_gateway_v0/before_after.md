# Bảng tổng hợp trước/sau

| CWE | Vị trí | Trạng thái v0 | Trạng thái v1 | Công cụ xác minh |
|---|---|---|---|---|
| CWE-667 | AG(!(webhook_locked & recon_locked)) | AG(!(webhook_locked & recon_locked)) sai; phản ví dụ: ledger_free -> webhook_holds -> lock_conflict | — | Kripke, BMC (Z3) |
| CWE-693 | AG(!violation) | AG(!violation) sai; phản ví dụ: ledger_free -> webhook_holds -> lock_conflict | — | CTL, BMC (Z3) |
| CWE-693 | AG(shipped -> paid) | AG(shipped -> paid) sai; phản ví dụ: CREATED -> PENDING -> UNKNOWN -> SHIPPED_UNPAID | — | CTL, BMC (Z3) |
| CWE-693 | AG(timeout -> AF(paid \| failed)) | AG(timeout -> AF(paid \| failed)) sai; phản ví dụ: CREATED -> PENDING -> UNKNOWN -> UNKNOWN | — | CTL |
| CWE-693 | AG(!double_capture) | AG(!double_capture) sai; phản ví dụ: CREATED -> PENDING -> SUCCEEDED -> DUPLICATE_CAPTURE | — | CTL, BMC (Z3) |
| CWE-693 | AG(refunding -> AF(refunded)) | AG(refunding -> AF(refunded)) sai; phản ví dụ: CREATED -> PENDING -> SUCCEEDED -> REFUNDING -> REFUNDING | — | CTL |
| CWE-833 | Mô hình trạng thái | Trạng thái deadlock: REFUNDING | — | Kripke |
| CWE-120 | parse_webhook_signature | Scanner: dangerous-function tại dòng 9 (`strcpy(buffer, raw_signature); /* khong kiem tra kich thuoc dich */`) | Scanner v1: 0 finding; Sanitizer v1: sạch | Static scanner, ASan/UBSan |
| CWE-401 | write_audit_log | Scanner: memory-leak tại dòng 12 (`return 0; /* thoat ma khong free */`) | Scanner v1: 0 finding; Sanitizer v1: sạch | Static scanner |
| CWE-415 | close_payment_session | Scanner: double-free tại dòng 13 (`free(data); /* giai phong lan thu hai */`) | Scanner v1: 0 finding; Sanitizer v1: sạch | Static scanner, ASan/UBSan |
| CWE-416 | release_card_token_buffer | Scanner: use-after-free tại dòng 12 (`data[0] = 'A'; /* ghi sau khi da free */`) | Scanner v1: 0 finding; Sanitizer v1: sạch | Static scanner, ASan/UBSan |
| CWE-190 | calculate_total_payment | Sanitizer: signed-integer-overflow tại dòng 5 với input (INT_MAX, 1) | Scanner v1: 0 finding; Sanitizer v1: sạch | ASan/UBSan |
| CWE-190 | order_total_counter | Z3 SAT: {'amount': 2147483647, 'shipping_fee': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2147204848 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | daily_transaction_counter | Z3 SAT: {'tx_today': 2147483647, 'tx_backlog': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2129640465 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | active_session_counter | Z3 SAT: {'active_sessions': 2147483647, 'pending_sessions': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2145843031 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | refund_total_vnd | Z3 SAT: {'refunded_vnd': 2147483647, 'pending_refund_vnd': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2143285231 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | webhook_retry_counter | Z3 SAT: {'retries_today': 2147483647, 'retries_backlog': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2111565480 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-190 | settlement_batch_bytes | Z3 SAT: {'batch_bytes': 2147483647, 'header_bytes': 1} → giá trị đúng 2147483648; bit-vector 32-bit wrap-around = -2145771516 | Z3 UNSAT với tiền điều kiện của v1 | Z3 |
| CWE-369 | refund_ratio | blackbox: ZeroDivisionError ở lần thử 48/2000, input (2147483646, 0) | blackbox v1: 0/2000 lỗi; coverage v1: 0/2000 lỗi; concolic v1: 0/3 lỗi | Fuzzing (blackbox), Fuzzing (coverage), Fuzzing (concolic) |
| CWE-798 | webhook_bypass_token | concolic: bypass ở lần thử 4/2000, input (7788, 9999) | blackbox v1: 0/2000 lỗi; coverage v1: 0/2000 lỗi; concolic v1: 0/1 lỗi | Fuzzing (concolic) |
| CWE-798 | support_override_pin | concolic: bypass ở lần thử 4/2000, input (4821, 7306) | blackbox v1: 0/2000 lỗi; coverage v1: 0/2000 lỗi; concolic v1: 0/1 lỗi | Fuzzing (concolic) |
