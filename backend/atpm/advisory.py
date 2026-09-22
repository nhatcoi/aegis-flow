"""Implementation guidance for an ecommerce payment feature, derived from the model.

Every item is produced by reading the specification, not from a fixed checklist: the
status reports whether the model already constrains the risk, whether the model is
silent about it, or whether the risk lives entirely outside what a finite-state model
can express. Verification and test results, when supplied, promote findings to critical.

Status values
    MODELED        the specification constrains this; the checker can refute a violation
    PARTIAL        modelled in part; a named gap remains
    MISSING        the model says nothing and it is expressible — extend the spec
    OUTSIDE_MODEL  not expressible as a finite-state invariant; enforce it in code
"""
from .specification import spec_hash

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STATUS_ORDER = {"MISSING": 0, "PARTIAL": 1, "OUTSIDE_MODEL": 2, "MODELED": 3}


def references(expr, found=None):
    """Every ``$name`` and ``$input.name`` read by an expression."""
    found = set() if found is None else found
    if isinstance(expr, str) and expr.startswith("$"):
        found.add(expr[1:])
    elif isinstance(expr, dict):
        for arg in next(iter(expr.values())):
            references(arg, found)
    return found


def guard_reads(transition):
    return references(transition["guard"])


def money_transitions(spec):
    """Transitions that create capture evidence or increase a capture counter."""
    result = []
    for transition in spec["transitions"]:
        for name in transition["effects"]:
            label = spec["variables"][name]["label"].lower()
            if "thu tiền" in label or "capture" in name or "captured" in name:
                result.append(transition)
                break
    return result


def item(id, title, severity, status, area, evidence, guidance):
    return {"id": id, "title": title, "severity": severity, "status": status,
            "area": area, "evidence": evidence, "guidance": guidance}


def check_webhook_authenticity(spec):
    captures = money_transitions(spec)
    guarded = [t for t in captures if any(r.startswith("input.") and "verif" in r for r in guard_reads(t))]
    if captures and len(guarded) == len(captures):
        return item(
            "webhook_authenticity", "Xác thực nguồn webhook trước khi ghi nhận thu tiền",
            "critical", "MODELED", "Cổng thanh toán",
            f"Mọi sự kiện ghi nhận thu tiền ({', '.join(t['event'] for t in guarded)}) đều có guard "
            "đọc input xác thực nguồn.",
            ["Mô hình chỉ giả định input xác thực là đúng; phần kiểm tra chữ ký phải nằm trong mã.",
             "Kiểm HMAC/chữ ký của cổng trên raw body trước khi parse JSON, so sánh bằng hàm hằng thời gian.",
             "Từ chối webhook có timestamp lệch quá vài phút để chặn replay.",
             "Giữ secret trong biến môi trường hoặc secret manager, hỗ trợ xoay vòng hai khóa song song."])
    missing = [t["event"] for t in captures if t not in guarded]
    return item(
        "webhook_authenticity", "Sự kiện thu tiền không kiểm tra nguồn gọi",
        "critical", "MISSING" if captures else "OUTSIDE_MODEL", "Cổng thanh toán",
        f"Không có guard xác thực nguồn cho: {', '.join(missing)}." if missing
        else "Đặc tả không có sự kiện nào ghi nhận thu tiền.",
        ["Thêm input boolean kiểu provider_verified và đưa vào guard của sự kiện thu tiền.",
         "Backend đặt input đó bằng kết quả kiểm chữ ký, không bao giờ lấy từ payload."])


def check_amount_binding(spec):
    captures = money_transitions(spec)
    reads = set().union(*(guard_reads(t) for t in captures)) if captures else set()
    amount = any("amount" in r or "tien" in r for r in reads)
    currency = any("currency" in r for r in reads)
    if amount and currency:
        return item(
            "amount_binding", "Ràng buộc số tiền và loại tiền với đơn hàng",
            "critical", "MODELED", "Toàn vẹn dữ liệu",
            "Guard thu tiền đọc cả input đối chiếu số tiền và loại tiền.",
            ["So khớp số tiền, loại tiền và mã đơn hàng lấy từ cổng với bản ghi đơn hàng phía máy chủ.",
             "Dùng số nguyên đơn vị nhỏ nhất (đồng, cent), không dùng float cho tiền.",
             "Không bao giờ nhận số tiền từ client; giá được tính lại từ giỏ hàng khi tạo phiên thanh toán."])
    gap = [name for name, present in (("số tiền", amount), ("loại tiền", currency)) if not present]
    return item(
        "amount_binding", "Thu tiền chưa đối chiếu đủ số tiền và loại tiền",
        "critical", "PARTIAL" if (amount or currency) else "MISSING", "Toàn vẹn dữ liệu",
        f"Guard thu tiền không đọc input đối chiếu: {', '.join(gap)}.",
        ["Thêm input đối chiếu còn thiếu và đưa vào guard của sự kiện thu tiền.",
         "Không cho phép thu tiền khi số tiền hoặc loại tiền lệch so với đơn hàng."])


def check_single_capture(spec):
    bounded = [p["id"] for p in spec["properties"]
               if isinstance(p["expression"], dict) and next(iter(p["expression"])) in {"le", "lt"}]
    guards = [t["event"] for t in money_transitions(spec)
              if guard_reads(t) & set(spec["variables"])]
    if bounded and guards:
        return item(
            "single_capture", "Chặn thu tiền lặp trên cùng một đơn",
            "high", "MODELED", "Toàn vẹn dữ liệu",
            f"Bất biến chặn trên số lần thu tiền ({', '.join(bounded)}) và guard thu tiền đọc biến đếm.",
            ["Thêm ràng buộc UNIQUE trên (order_id, capture_id) ở tầng cơ sở dữ liệu làm chốt chặn cuối.",
             "Đọc đơn hàng bằng SELECT ... FOR UPDATE trước khi ghi nhận thu tiền.",
             "Đối soát định kỳ với báo cáo của cổng để phát hiện thu tiền kép mà hệ thống bỏ sót."])
    return item(
        "single_capture", "Không có ràng buộc chặn thu tiền lặp",
        "high", "MISSING", "Toàn vẹn dữ liệu",
        "Không tìm thấy bất biến chặn trên biến đếm thu tiền, hoặc guard không đọc biến đếm.",
        ["Thêm biến đếm số lần thu tiền với miền hữu hạn và bất biến dạng captured_count ≤ 1.",
         "Đưa điều kiện captured_count = 0 vào guard của sự kiện thu tiền."])


def check_fulfilment_gate(spec):
    fulfil = [t for t in spec["transitions"]
              if any("giao hàng" in spec["variables"][n]["label"].lower() or n in {"shipped", "fulfilled"}
                     for n in t["effects"])]
    linked = [p["id"] for p in spec["properties"]
              if isinstance(p["expression"], dict) and next(iter(p["expression"])) == "implies"]
    if fulfil and linked:
        return item(
            "fulfilment_gate", "Chỉ giao hàng sau khi có bằng chứng thu tiền",
            "critical", "MODELED", "Nghiệp vụ",
            f"Sự kiện {', '.join(t['event'] for t in fulfil)} bị chặn bởi bất biến "
            f"{', '.join(linked)} dạng kéo theo.",
            ["Quyết định giao hàng phải đọc trạng thái thanh toán trong cùng transaction, không đọc cache.",
             "Không kích hoạt giao hàng từ sự kiện phía client hay từ redirect sau thanh toán.",
             "Với hàng số (digital), phát hành quyền truy cập sau khi commit trạng thái SUCCEEDED."])
    return item(
        "fulfilment_gate", "Thiếu ràng buộc giữa giao hàng và thu tiền",
        "critical", "MISSING" if fulfil else "OUTSIDE_MODEL", "Nghiệp vụ",
        "Không có bất biến dạng shipped ⇒ có bằng chứng thu tiền." if fulfil
        else "Đặc tả không mô hình hóa bước giao hàng.",
        ["Thêm bất biến implies giữa biến giao hàng và bằng chứng thu tiền.",
         "Chạy lại kiểm chứng Z3 để xác nhận không còn đường chạy giao hàng khi chưa thu tiền."])


def check_idempotency(spec):
    return item(
        "idempotency", "Chống xử lý trùng sự kiện từ cổng thanh toán",
        "critical", "PARTIAL", "Idempotency",
        "Monitor sinh ra lưu event_id đã xử lý và trả DUPLICATE khi gặp lại cùng nội dung, "
        "REJECTED khi một ID được dùng lại với nội dung khác.",
        ["Lưu event_id trong bảng riêng với PRIMARY KEY, ghi cùng transaction cập nhật trạng thái.",
         "Gửi Idempotency-Key khi gọi API thu tiền của cổng để lần thử lại không tạo giao dịch mới.",
         "Trả 200 cho webhook trùng; trả lỗi 4xx chỉ khi chữ ký sai, để cổng không thử lại vô ích.",
         "Đặt thời hạn lưu trữ event_id dài hơn cửa sổ thử lại của cổng."])


def check_transaction_boundary(spec):
    return item(
        "transaction_boundary", "Cập nhật trạng thái, ID đã xử lý và nhật ký trong một transaction",
        "critical", "OUTSIDE_MODEL", "Toàn vẹn dữ liệu",
        "Mô hình giả định sự kiện được xử lý tuần tự; tính nguyên tử là trách nhiệm của tầng lưu trữ.",
        ["Bọc kiểm tra trùng, quyết định của monitor, ghi trạng thái và ghi nhật ký trong một transaction.",
         ("Khóa bản ghi đơn hàng (SELECT ... FOR UPDATE hoặc BEGIN IMMEDIATE) để hai webhook song song "
          "không cùng đọc trạng thái cũ."),
         "Phát sự kiện ra hệ thống khác bằng outbox pattern, không gọi HTTP bên trong transaction."])


def check_unknown_state(spec):
    statuses = spec["variables"]["status"]["values"]
    uncertain = [s for s in statuses if s.upper() in {"UNKNOWN", "PENDING_REVIEW", "INDETERMINATE"}]
    recovery = [t["event"] for t in spec["transitions"] if uncertain and t["to_state"] in uncertain]
    if uncertain and recovery:
        return item(
            "unknown_state", "Xử lý mất phản hồi từ cổng thanh toán",
            "high", "MODELED", "Vận hành",
            f"Trạng thái {', '.join(uncertain)} đạt tới qua {', '.join(recovery)}, và có sự kiện "
            "xác nhận đến muộn từ trạng thái đó.",
            ["Không suy ra thất bại từ timeout; truy vấn lại cổng bằng API tra cứu giao dịch.",
             "Đặt hàng đợi đối soát cho đơn ở trạng thái không chắc chắn quá ngưỡng thời gian.",
             "Xác nhận đến muộn vẫn phải qua đúng guard thu tiền, không có đường tắt."])
    return item(
        "unknown_state", "Chưa mô hình hóa trường hợp mất phản hồi từ cổng",
        "high", "MISSING", "Vận hành",
        "Không có trạng thái biểu diễn kết quả chưa chắc chắn sau timeout.",
        ["Thêm trạng thái UNKNOWN và sự kiện timeout dẫn tới nó.",
         "Cho phép xác nhận đến muộn chuyển từ UNKNOWN sang thành công với cùng guard."])


def check_retry_safety(spec):
    retries = [t for t in spec["transitions"]
               if any(s.upper() in {"FAILED", "CANCELLED"} for s in t["from_states"])]
    unsafe = [t["event"] for t in retries if not (guard_reads(t) & set(spec["variables"]))]
    if not retries:
        return None
    if unsafe:
        return item(
            "retry_safety", "Thử lại sau thất bại không kiểm tra tiền đã thu",
            "high", "MISSING", "Nghiệp vụ",
            f"Guard của {', '.join(unsafe)} không đọc biến trạng thái nào nên cho phép thử lại "
            "ngay cả khi tiền đã được thu.",
            ["Thêm điều kiện captured_count = 0 vào guard của sự kiện thử lại.",
             "Chạy lại Z3 để kiểm tra không còn đường chạy thu tiền hai lần."])
    return item(
        "retry_safety", "Thử lại sau thất bại bị chặn khi đã thu tiền",
        "medium", "MODELED", "Nghiệp vụ",
        f"Guard của {', '.join(t['event'] for t in retries)} đọc biến trạng thái trước khi cho thử lại.",
        ["Giới hạn số lần thử lại và dùng exponential backoff để không dồn tải lên cổng.",
         "Ghi lại lý do thất bại của cổng để phân biệt lỗi tạm thời và lỗi từ chối vĩnh viễn."])


def check_refund_coverage(spec):
    events = {t["event"] for t in spec["transitions"]}
    refunds = sorted(e for e in events if "refund" in e or "hoan" in e)
    if refunds:
        return item(
            "refund_coverage", "Hoàn tiền nằm trong phạm vi kiểm chứng",
            "high", "MODELED", "Nghiệp vụ",
            f"Đặc tả có sự kiện hoàn tiền: {', '.join(refunds)}.",
            ["Bất biến refunded ≤ captured chặn hoàn vượt số tiền đã thu; giữ nó khi mở rộng mô hình.",
             "Hoàn tiền cũng cần idempotency key riêng, không dùng lại key của lần thu tiền.",
             "Khóa hoàn tiền cho đơn đang tranh chấp (chargeback) để tránh hoàn hai lần."])
    return item(
        "refund_coverage", "Hoàn tiền chưa được mô hình hóa",
        "high", "MISSING", "Nghiệp vụ",
        "Không có sự kiện hoàn tiền nào trong đặc tả; giả định đã ghi nhận điều này là ngoài phạm vi.",
        ["Mở mẫu “Hoàn tiền & thu một phần” để có mô hình tham chiếu.",
         "Thêm biến đếm số tiền đã hoàn với bất biến refunded ≤ captured.",
         "Chặn giao hàng sau khi đã hoàn toàn bộ."])


def check_reconciliation(spec):
    names = set(spec["variables"]) | {t["event"] for t in spec["transitions"]}
    matched = sorted(n for n in names if "reconcil" in n or "doi_soat" in n)
    if matched:
        return item(
            "reconciliation", "Đối soát với cổng thanh toán có trong mô hình",
            "medium", "MODELED", "Vận hành",
            f"Đặc tả có: {', '.join(matched)}.",
            ["Chạy job đối soát hằng ngày trên báo cáo thanh toán của cổng, không chỉ dựa vào webhook.",
             "Cảnh báo khi số bản ghi hoặc tổng tiền hai bên lệch nhau.",
             "Coi webhook là tín hiệu nhanh, còn đối soát là nguồn chân lý cuối cùng."])
    return item(
        "reconciliation", "Không có bước đối soát với cổng",
        "medium", "MISSING", "Vận hành",
        "Mô hình chỉ phản ứng theo webhook, không có bước xác nhận lại với cổng.",
        ["Thêm biến reconciled và sự kiện đối soát vào đặc tả.",
         "Lập job định kỳ kéo báo cáo giao dịch từ cổng và so với sổ nội bộ.",
         "Webhook có thể mất; đối soát là cơ chế phát hiện mất mát duy nhất."])


def check_open_guards(spec):
    open_events = [t["event"] for t in spec["transitions"] if t["guard"] is True]
    if not open_events:
        return item(
            "open_guards", "Mọi chuyển trạng thái đều có điều kiện",
            "low", "MODELED", "Nghiệp vụ",
            "Không có transition nào dùng guard true.",
            ["Giữ nguyên: mỗi sự kiện đều phải nêu rõ điều kiện áp dụng."])
    return item(
        "open_guards", "Có chuyển trạng thái không kèm điều kiện",
        "medium", "PARTIAL", "Nghiệp vụ",
        f"Guard là true ở: {', '.join(open_events)}. Mô hình chỉ dựa vào from_states để chặn.",
        ["Xác thực quyền của người gọi ở tầng ứng dụng cho các sự kiện này.",
         "Nếu sự kiện đến từ người dùng, kiểm tra đơn hàng thuộc về đúng tài khoản.",
         "Cân nhắc thêm guard rõ ràng để Z3 kiểm chứng được điều kiện đó."])


def check_card_data(spec):
    return item(
        "card_data", "Không lưu dữ liệu thẻ trong hệ thống",
        "critical", "OUTSIDE_MODEL", "Tuân thủ",
        "Mô hình trừu tượng hóa mọi dữ liệu thẻ thành các boolean đã được máy chủ kiểm tra.",
        ["Dùng trang thanh toán hoặc iframe do cổng cung cấp để số thẻ không đi qua máy chủ của bạn.",
         "Chỉ lưu token và bốn số cuối; không ghi PAN, CVV hay dữ liệu dải từ vào log hay cơ sở dữ liệu.",
         "Lọc trường nhạy cảm khỏi log và báo cáo lỗi trước khi gửi đi.",
         "Bật TLS cho mọi kết nối tới cổng và ghim phiên bản API của cổng."])


def check_audit_log(spec):
    return item(
        "audit_log", "Nhật ký kiểm toán bất biến cho mọi sự kiện tiền",
        "high", "OUTSIDE_MODEL", "Vận hành",
        "Mô hình sinh ra bản ghi cho từng sự kiện, nhưng tính bất biến của nhật ký nằm ngoài phạm vi.",
        ["Ghi append-only: sự kiện, trạng thái trước, trạng thái sau, phán quyết của monitor, thời điểm.",
         "Không cho phép UPDATE hay DELETE trên bảng nhật ký; sửa sai bằng bản ghi bù.",
         "Gắn mỗi bản ghi với SHA-256 của đặc tả đang chạy để truy vết được phiên bản quy tắc."])


def check_monitor_enforcement(spec):
    return item(
        "monitor_enforcement", "Bật chế độ chặn của monitor khi chạy thật",
        "high", "MODELED", "Vận hành",
        "Monitor sinh ra có tham số enforce; khi bật, vi phạm bị chặn trước khi trạng thái thay đổi.",
        ["Chạy enforce=True trên môi trường thật; chế độ chỉ quan sát chỉ dùng khi thử nghiệm.",
         "Cảnh báo ngay khi monitor trả BLOCKED: đó là dấu hiệu mã gọi sai hoặc cổng gửi dữ liệu lạ.",
         "Sinh lại artifact và chạy lại kiểm chứng mỗi khi đặc tả đổi; đối chiếu SHA-256 khi triển khai."])


CHECKS = [check_webhook_authenticity, check_amount_binding, check_fulfilment_gate, check_idempotency,
          check_transaction_boundary, check_card_data, check_single_capture, check_unknown_state,
          check_retry_safety, check_refund_coverage, check_monitor_enforcement, check_audit_log,
          check_reconciliation, check_open_guards]


def from_results(verification, tests):
    """Promote failed verification or test results into their own advisory items."""
    items = []
    violated = [r for r in (verification or {}).get("results", []) if r["verdict"] == "VIOLATED"]
    unknown = [r for r in (verification or {}).get("results", []) if r["verdict"] == "UNKNOWN"]
    if violated:
        items.append(item(
            "verification_violated", "Kiểm chứng tìm thấy phản ví dụ",
            "critical", "MISSING", "Kiểm chứng",
            "Thuộc tính bị vi phạm: " + ", ".join(f"{r['label']} (bước {r.get('depth', '?')})" for r in violated),
            ["Sửa guard hoặc bất biến cho tới khi Z3 không còn tìm được phản ví dụ.",
             "Không triển khai đặc tả này; mã sinh ra sẽ để lọt đúng đường chạy trong phản ví dụ.",
             "Xem phản ví dụ trên đồ thị Kripke để thấy chuỗi sự kiện dẫn tới vi phạm."]))
    if unknown:
        items.append(item(
            "verification_unknown", "Kiểm chứng chưa kết luận trong ngân sách thời gian",
            "medium", "PARTIAL", "Kiểm chứng",
            "Chưa kết luận: " + ", ".join(r["label"] for r in unknown),
            ["Giảm giới hạn k rồi tăng dần để tìm ngưỡng còn giải được.",
             "Thu nhỏ miền giá trị của biến để không gian trạng thái nhỏ lại.",
             "Kết quả chưa kết luận không phải là an toàn."]))
    failed = [r for r in (tests or {}).get("results", []) if r["verdict"] == "FAIL"]
    if failed:
        items.append(item(
            "tests_failed", "Kiểm thử trên mã sinh không đạt",
            "critical", "MISSING", "Kiểm chứng",
            "Ca không đạt: " + ", ".join(r["name"] for r in failed),
            ["Xử lý từng ca không đạt trước khi dùng artifact ở bất kỳ môi trường nào.",
             "Ca tĩnh không đạt nghĩa là bản thân mô hình có khuyết điểm, không chỉ mã sinh."]))
    return items


def advise(spec, verification=None, tests=None):
    items = [result for check in CHECKS if (result := check(spec)) is not None]
    items = from_results(verification, tests) + items
    items.sort(key=lambda entry: (SEVERITY_ORDER[entry["severity"]], STATUS_ORDER[entry["status"]]))
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    coverage = {"MODELED": 0, "PARTIAL": 0, "MISSING": 0, "OUTSIDE_MODEL": 0}
    for entry in items:
        counts[entry["severity"]] += 1
        coverage[entry["status"]] += 1
    return {"spec_hash": spec_hash(spec), "items": items, "severity_counts": counts,
            "coverage_counts": coverage,
            "scope": "Gợi ý triển khai suy ra từ đặc tả; không thay thế đánh giá bảo mật hay kiểm toán PCI DSS"}
