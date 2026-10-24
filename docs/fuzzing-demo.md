# Trình bày Chương 4 trên AegisFlow

Tab Ch.4 hiển thị bằng chứng sau khi chạy pipeline. Sáu bước cho phép lần lượt xem lại quá trình; nút Bước trước/Bước tiếp không thực thi lại chương trình. Nút Replay ở bước 5 mới chạy lại input đã chọn.

## 1. Mở và chạy

```bash
uv run python main.py
```

1. Chọn `payment_gateway_v0_spec.xlsx`.
2. Mở cấu hình ⚙: seed = 1, ngân sách = 2.000, concolic BFS, timeout Z3 fuzzing = 1.000 ms.
3. Bấm Chạy pipeline và chờ hoàn tất.
4. Mở tab Ch.4 Fuzzing. Bảng phía trên có ba nhóm: Thực thi hàm Python, Chuỗi trạng thái trên mô hình đặc tả và C · ASan/UBSan.
5. Chọn một dòng chiến dịch. Phía dưới hiển thị quy trình 6 bước của đúng hàm, phiên bản và chiến lược đó.

Một đặc tả có thể sinh cả mã v0 và mã v1; cột Bản cho biết biến thể đang được chạy. Chạy file đặc tả v1 riêng còn kiểm tra thiết kế trạng thái đã sửa.

## 2. Input và output của từng bước

| Bước trên giao diện | Input | Phần mềm thực hiện | Output quan sát được |
| --- | --- | --- | --- |
| 1. Chuẩn bị | Target, mã v0/v1, seed, budget, BFS/DFS và timeout Z3 | Chạy chiến dịch từ cấu hình trên thanh công cụ | Tên hàm, miền int32, oracle, số lần thực thi và lý do kết thúc |
| 2. Sinh input | Số ngẫu nhiên, seed corpus hoặc model SAT | Sinh tuple tham số; đột biến input cha hoặc lấy giá trị từ solver | Timeline từng tuple; nguồn sinh, input cha, phép đột biến, dòng mới và oracle |
| 3. Thực thi · Coverage | Một dòng timeline đang chọn | Gọi hàm thật, theo dõi dòng mã bằng tracer, đánh giá oracle | Giá trị trả về hoặc exception/bypass; trace thứ tự dòng; mã tô màu và biểu đồ số dòng đã phủ |
| 4. Đường đi · Z3 | Path condition của lần chạy | Giữ tiền tố, phủ định một điều kiện, giải ràng buộc int32 | SAT/UNSAT/UNKNOWN, model, tuple mới, truy vấn SMT-LIB và cây quan hệ sinh input |
| 5. Replay · v0/v1 | Tuple đã chọn ở bước 2 | Chạy chính tuple đó trên hai bản của hàm | Output, finding, traceback và hash mã của từng bản |
| 6. Bằng chứng · Demo | Toàn bộ dữ liệu chiến dịch và replay | Xuất vào một thư mục run riêng | Manifest, target.py, JSONL, corpus, crash, coverage, graph DOT, query/model và replay |

Black-box không sử dụng coverage để chọn input tiếp theo; tracer chỉ ghi bằng chứng. Coverage-guided sử dụng tập dòng đã chạy để giữ input mở thêm coverage. Concolic dùng điều kiện trong mã để tạo ràng buộc.

Coverage hiện là **line coverage theo số dòng**, không phải branch coverage hay tỷ lệ bao phủ mọi đường đi. Biểu đồ không chứng minh hàm an toàn.

## 3. Demo A — Lỗi chia cho 0

Chọn `refund_ratio`, v0, concolic. Có thể xem black-box/coverage trước để so sánh.

### Đầu vào ban đầu

```text
refund_amount = 1
total_amount  = 1
```

### Output khi chạy bình thường

```text
refund_ratio(1, 1) → 1
Oracle: không lỗi
Path condition: total_amount != 0
```

Ở bước 4, chọn truy vấn phủ định điều kiện mẫu số:

```text
Giữ miền tham số int32
Phủ định: total_amount != 0
Truy vấn mới: total_amount == 0
Kết quả: SAT
Model: total_amount = 0; refund_amount là giá trị int32 do solver chọn
```

Solver có thể chọn nhiều giá trị tử số khác nhau. Đọc tuple từ giao diện thay vì khẳng định tử số luôn bằng 1.

### Output của input được sinh

```text
refund_ratio(<tử số do solver chọn>, 0)
→ ZeroDivisionError
→ CWE-369
```

Ở bước 2, lọc “Chỉ có lỗi / vi phạm”, chọn input này rồi sang bước 3 xem dòng chia và traceback. Sang bước 5, bấm Replay:

```text
v0: ZeroDivisionError
v1: trả 0, không có finding với cùng input
```

Lời trình bày:

> “Input đầu tiên chạy bình thường. Từ điều kiện mẫu số khác 0, công cụ phủ định điều kiện và dùng Z3 sinh mẫu số 0. Em chạy input đó trên mã thật để xác nhận lỗi, rồi replay cùng input trên bản sửa.”

## 4. Demo B — Magic value và model sinh input mới

Chọn `webhook_bypass_token`, v0. Trước tiên mở hai dòng blackbox và coverage, sau đó chọn concolic.

### Mục tiêu

```python
if header_token == 7788:
    if secret_token == 9999:
        return True
return False
```

Trong ví dụ này, True được oracle của hàm magic_value coi là đạt nhánh bypass. Các cặp hardcode là dữ liệu mẫu cài chủ đích.

### Chuỗi input/output

| Tình huống | Input | Output / đường đi |
| --- | --- | --- |
| Seed đầu tiên | `(1, 1)` | False; `header_token != 7788` |
| Phủ định điều kiện đầu | `(7788, y)` do solver chọn | Nếu `y != 9999`, False; đi sâu thêm một nhánh |
| Giữ tiền tố, phủ định điều kiện hai | `(7788, 9999)` | True; oracle ghi bypass/CWE-798 |

Mở bước 4 và chọn node truy vấn có model `{header_token: 7788, secret_token: 9999}`. Cho giáo viên xem:

1. Path condition ban đầu.
2. Nhánh được phủ định và các điều kiện tiền tố giữ lại.
3. Ràng buộc miền int32 trong SMT-LIB.
4. Trạng thái SAT và model.
5. Input thực thi được nối với query trong cây sinh input.
6. Output True của chính input đó ở bước 3.

Không gọi model Z3 là một hệ thống thanh toán mới: đây là phép gán giá trị thỏa ràng buộc để sinh input.

### Replay bản sửa

Chọn input bypass ở bước 2, mở bước 5 và bấm Replay. Với cấu hình mặc định chưa đặt WEBHOOK_SECRET, bản sửa từ chối và trả False. Nếu môi trường có bí mật cấu hình, đọc output thực tế; True với thông tin xác thực hợp lệ cần được diễn giải theo chính sách oracle, không tự động suy ra cửa hậu.

Bản v1 đã được hỗ trợ mô hình `os.environ.get` với tên khóa cố định và `hmac.compare_digest`
cho cặp số int32 định dạng thập phân `a:b`. Khi chưa đặt WEBHOOK_SECRET, nhánh từ chối được thực thi,
query đảo nhánh trả UNSAT và chiến dịch có thể kết thúc sau một input vì không còn đường khả thi
trong cấu hình đó. Khi có cấu hình, solver khám phá kết quả khớp/không khớp; xác thực đúng bí mật
không bị oracle coi là bypass. Xem mục “giả định / phạm vi” ở bước 1: kết luận chỉ áp dụng cho
cấu hình cố định của chiến dịch, không phải mọi biến môi trường hoặc tính chất timing của hmac.
Các cú pháp/lời gọi thư viện ngoài phạm vi này vẫn báo **CHƯA ĐỦ KẾT LUẬN** khi chưa có mô hình.

Lời trình bày:

> “Ngẫu nhiên không có hướng dẫn để đạt đúng hai hằng số. Concolic đọc điều kiện nhánh, dùng solver tạo input có chủ đích và thực thi lại. Model SAT là bằng chứng sinh input; kết quả chạy mới xác nhận bypass trong oracle của ví dụ.”

## 5. Demo C — Khám phá chuỗi trạng thái

Chọn nhóm “Chuỗi trạng thái · mô hình đặc tả”, chọn BFS hoặc DFS.

Ví dụ chuỗi:

```text
CREATED → PENDING → UNKNOWN → SHIPPED_UNPAID
```

Input là một chuỗi trạng thái của đặc tả. Output là kết quả kiểm tra các nhãn/invariant và chuyển tiếp trên mô hình:

```text
3 chuyển tiếp, 4 trạng thái trên chuỗi
SHIPPED_UNPAID có nhãn vi phạm / shipped mà chưa paid
Oracle: invariant_violation
```

Bước 2 liệt kê các chuỗi thực sự đã lấy ra đánh giá. Bước 3 hiển thị state/transition count. Bước 4 hiển thị cây tiền tố của các chuỗi. Bước 5 đánh giá lại đúng chuỗi trên cùng mô hình, không gọi API thanh toán thật.

BFS dùng hàng đợi; DFS dùng ngăn xếp. Độ sâu đếm số cạnh. BFS/DFS giới hạn số lần lặp lại mỗi trạng thái trên một path; vì vậy “duyệt xong” vẫn thuộc phạm vi giới hạn này. Coverage không tính các trạng thái/cạnh mới chỉ được đưa vào hàng đợi.

Không diễn giải một chuỗi hữu hạn ở UNKNOWN là chứng minh chờ vô hạn. Dùng phản ví dụ lasso từ CTL cho yêu cầu sống còn đó.

## 6. Đọc kết luận chính xác

- **TÌM THẤY LỖI:** có input thực thi gây finding. Xem tổng hit và nhóm lỗi; nhiều hit không có nghĩa nhiều nguyên nhân gốc độc lập.
- **CHƯA THẤY LỖI TRONG PHẠM VI CHẠY:** đọc số lần chạy, ngân sách và lý do dừng. Không có chứng minh an toàn tổng quát.
- **CHƯA ĐỦ KẾT LUẬN:** gặp cú pháp/thư viện chưa hỗ trợ hoặc solver không kết luận.
- **UNSAT của một query:** chỉ nói đường đã mã hóa bất khả thi trong miền ràng buộc; không kết luận toàn chương trình an toàn.
- Cây ở bước 4 là quan hệ sinh input hoặc cây khám phá mô hình. Đây không phải CFG đầy đủ của mọi hành vi chương trình.
- GUI hiện xem lại dữ liệu chiến dịch sau khi pipeline hoàn tất. Chưa có chế độ tạm dừng thực thi từng lệnh hoặc chạy fuzzing trên API thanh toán thật.
- Thời gian chạy có bao gồm chi phí ghi trace và, với concolic, solver. Các con số này thuộc engine minh họa, không phải benchmark AFL/libFuzzer.

## 7. Xuất bằng chứng và trình bày file

Bấm Xuất ở bước 6. Mỗi lần xuất tạo một thư mục riêng, giữ các lần xuất trước:

```text
results/<spec>/fuzz_runs/<run_id>/
  manifest.json                cấu hình, hash đặc tả và danh sách chiến dịch
  replay_results.json          các lần replay đã bấm, kèm hash mã
  state_exploration.json       tất cả chuỗi mô hình đã đánh giá
  000_v0_blackbox/
    campaign.json              target, seed, budget, số lần chạy, lý do dừng
    target.py                  mã nguồn của đúng phiên bản
    events.jsonl               toàn bộ lần thực thi, gồm input và trace
    crashes.json               tất cả lần thử gây finding
    corpus.json                input được coverage-guided giữ lại (nếu có)
    coverage.json              tập dòng và lịch sử tăng coverage
    inputs.dot                 đồ thị quan hệ sinh input
    queries/q1.smt2             truy vấn SMT-LIB của concolic (nếu có)
    queries/q1.json             trạng thái solver, model, input sinh ra
```

Timeline trên GUI phân trang 100 dòng. File JSONL không cắt 50/200 sự kiện như phần xem trước cũ. `fuzz_runs/latest.txt` chỉ run xuất gần nhất. Các file log/CSV cũ vẫn được xuất để tương thích.

Để nộp bằng chứng đầy đủ có sanitizer và so sánh hai đặc tả:

```bash
uv run python -m core.pipeline \
  dataset/specs_excel/payment_gateway_v0_spec.xlsx \
  --compare dataset/specs_excel/payment_gateway_v1_spec.xlsx \
  --seed 1 --budget 2000 --fuzz-search bfs --fuzz-solver-timeout 1000
```

Replay thao tác từ GUI sẽ được lưu khi xuất sau đó. CLI không tự bấm replay nên replay_results.json có thể rỗng; input và query để chạy lại vẫn được lưu đầy đủ.

## 8. Phân chia thuyết trình 6–7 phút

1. 45 giây: mục tiêu và cấu hình chiến dịch; giải thích oracle.
2. 60 giây: refund_ratio, input 0 ở mẫu số, trace và exception.
3. 2 phút: so sánh ba chiến lược trên magic value; mở query/model và input được sinh.
4. 45 giây: replay input trên hai bản, đọc output thực tế.
5. 45 giây: chuỗi trạng thái và ranh giới giữa mô hình với mã chạy.
6. 45 giây: xuất thư mục bằng chứng, chỉ đường từ kết quả tới query/input/trace.
7. 30 giây: giới hạn, đặc biệt unsupported và ý nghĩa “chưa thấy lỗi”.

Câu kết: “Phần Chương 4 cho thấy input được sinh từ đâu, chạy qua đâu, output thế nào và cách tái hiện. Các kết luận đều gắn với phạm vi chạy; CTL/BMC/SMT bổ sung các bảo đảm mà fuzzing hữu hạn không cung cấp.”

## 9. Fuzzing C có ASan/UBSan

Ch.4 có thêm nhóm **C · ASan/UBSan**. Trong cấu hình ⚙, đặt ngân sách C (mặc định 32 input
cho mỗi hàm và mỗi phiên bản; 0 = tắt). Timeout dùng chung mục Timeout sanitizer.

```text
Hàm C + seed + ngân sách
  → biên dịch với -fsanitize=address,undefined
  → sinh input biên, sau đó ngẫu nhiên có seed
  → mỗi input chạy qua stdin trong một tiến trình riêng
  → ASan/UBSan chẩn đoán lỗi
  → lưu stdin chính xác + log + mã nguồn/harness + cấu hình
```

1. Chọn `parse_webhook_signature`, v0 trong nhóm C.
2. Xem các chuỗi dài 0, buffer_size−1, buffer_size, … đã thực sự chạy. Chuỗi có độ dài bằng
   buffer_size đã cần thêm byte NUL nên có thể gây tràn trong v0.
3. Chọn dòng có sanitizer detection, xem `stdin_hex` và log `stack-buffer-overflow`.
4. Mở Replay v0/v1, bấm Replay. Cùng bytes được chạy lại trên cả hai bản, có hash mã và log.
5. Xuất bằng chứng; mở `fuzz_runs/<run_id>/c_*/REPLAY.md` và `crash_*.stdin`/`crash_*.log`.

Chiến dịch dừng ở finding đầu tiên; cột Đã chạy/Budget hiển thị phạm vi thật. Đây là black-box,
không đo native coverage. Không có solver Z3 trong chiến dịch này. `arithmetic` sinh cặp int32
để UBSan bắt tràn số; `alloc_release` không nhận tham số nên fuzzer thay đổi số lần gọi từ 1 đến 8.
Thiếu compiler hoặc build lỗi là chưa đủ kết luận; timeout/exit bất thường không có chẩn đoán sanitizer
cũng là chưa đủ kết luận. Finding đã xuất trước timeout vẫn được giữ, kèm lý do dừng timeout.
Trên macOS LeakSanitizer bị tắt, vì vậy không lấy chiến dịch sạch làm xác nhận động CWE-401.
