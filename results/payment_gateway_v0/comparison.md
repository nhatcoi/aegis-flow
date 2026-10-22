# So sánh thiết kế: `payment_gateway_v0` → `payment_gateway_v1`

## Thuộc tính trên mô hình Kripke

| Thuộc tính | payment_gateway_v0 | payment_gateway_v1 | BMC |
|---|---|---|---|
| Kiểm tra Deadlock (Bế tắc) | VI PHẠM | ĐẠT | — |
| AG(!(webhook_locked & recon_locked)) | VI PHẠM (ledger_free → webhook_holds → lock_conflict) | ĐẠT | UNSAFE → SAFE (đạt CT) |
| AG(!(violation & safe)) | ĐẠT | ĐẠT | SAFE (đạt CT) → SAFE (đạt CT) |
| AG(!(processing & paid)) | ĐẠT | ĐẠT | SAFE (đạt CT) → SAFE (đạt CT) |
| AG(!(paid & failed)) | ĐẠT | ĐẠT | SAFE (đạt CT) → SAFE (đạt CT) |
| AG(!(timeout & paid)) | ĐẠT | ĐẠT | SAFE (đạt CT) → SAFE (đạt CT) |
| AG(!violation) | VI PHẠM (ledger_free → webhook_holds → lock_conflict) | ĐẠT | UNSAFE → SAFE (đạt CT) |
| safe -> EF(webhook_locked) | ĐẠT | ĐẠT | — |
| AG(shipped -> paid) | VI PHẠM (CREATED → PENDING → UNKNOWN → SHIPPED_UNPAID) | ĐẠT | UNSAFE → SAFE (đạt CT) |
| AG(timeout -> AF(paid \| failed)) | VI PHẠM (CREATED → PENDING → UNKNOWN → UNKNOWN) | ĐẠT | — |
| AG(!double_capture) | VI PHẠM (CREATED → PENDING → SUCCEEDED → DUPLICATE_CAPTURE) | ĐẠT | UNSAFE → SAFE (đạt CT) |
| created -> EF(shipped) | ĐẠT | ĐẠT | — |
| AG(refunding -> AF(refunded)) | VI PHẠM (CREATED → PENDING → SUCCEEDED → REFUNDING → REFUNDING) | ĐẠT | — |

## Test case

| ID | Tiêu đề | payment_gateway_v0 | payment_gateway_v1 |
|---|---|---|---|
| TC-1 | Worker webhook và worker đối soát tranh chấp khóa sổ cái | FAIL | PASS |
| TC-2 | Không giao hàng khi chưa thu tiền | FAIL | PASS |
| TC-3 | Timeout luôn được đối soát | FAIL | PASS |
| TC-4 | Cổng gửi lại webhook thu tiền | FAIL | PASS |
| TC-5 | Hoàn tiền luôn hoàn tất | FAIL | PASS |
| TC-6 | Chữ ký webhook dài bất thường | FAIL | PASS |
| TC-7 | Vòng đời bộ nhớ audit log / phiên / token thẻ | FAIL | PASS |
| TC-8 | Tổng tiền vượt int32 | PASS | PASS |
| TC-9 | Chứng minh tiền điều kiện chống tràn bằng Z3 | PASS | PASS |
| TC-10 | Tỷ lệ hoàn tiền với tổng tiền bằng 0 | FAIL | PASS |
| TC-11 | Tìm mã bí mật bằng concolic fuzzing | FAIL | PASS |
| TC-12 | Mã đơn hợp lệ không bị báo lỗi nhầm | PASS | PASS |

## Tổng hợp

| Đặc tả | Lỗ hổng có bằng chứng | Chưa vá | Chỉ khai báo | Test case PASS |
|---|---|---|---|---|
| payment_gateway_v0 | 20 | 7 | 1 | 3/12 |
| payment_gateway_v1 | 6 | 0 | 0 | 12/12 |
