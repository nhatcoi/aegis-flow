"""A small independent behavioral suite, executed against the generated artifact.

The scenarios are written against *roles* rather than fixed event names, so the same
suite runs on the basic payment model and on the extended refund model. A role that no
transition fills makes the scenarios depending on it report SKIP instead of FAIL.
"""
import time

from .advisory import references
from .analysis import static_checks
from .generation import generate, load_machine

UNCERTAIN = {"UNKNOWN", "PENDING_REVIEW", "INDETERMINATE"}


def role_of(spec):
    """Map scenario roles onto concrete event names declared by this specification.

    capture   sets the capture-evidence flag and reads a source-verification input
    ship      sets the fulfilment flag
    timeout   leads into a status that represents an uncertain gateway outcome
    refund    drives the model into a fully refunded status
    """
    roles = {}
    initial = spec["variables"]["status"]["initial"]
    for transition in spec["transitions"]:
        effects, event = transition["effects"], transition["event"]
        reads = references(transition["guard"])
        if initial in transition["from_states"] and "start" not in roles:
            roles["start"] = event
        # Prefer the full capture when a model offers both a full and a partial one.
        preferred = "capture" not in roles or effects.get("captured_units") == 2 or event == "confirm"
        if effects.get("capture_verified") is True and preferred and any("verif" in r for r in reads):
            roles["capture"] = event
        if effects.get("shipped") is True:
            roles["ship"] = event
        # A self-loop such as reconcile_refunded stays inside the status; it does not enter it.
        entering = transition["to_state"] not in transition["from_states"]
        if entering and transition["to_state"].upper() in UNCERTAIN:
            roles["timeout"] = event
        if entering and transition["to_state"].upper() == "REFUNDED" and "refund" not in roles:
            roles["refund"] = event
    return roles


def capture_counter(spec, roles):
    """The integer variable the capture event increases, if the model has one."""
    if "capture" not in roles:
        return None
    capture = next(t for t in spec["transitions"] if t["event"] == roles["capture"])
    for name in capture["effects"]:
        if type(spec["variables"][name]["initial"]) is int:
            return name
    return None


def exercise(spec):
    started = time.monotonic()
    artifact = generate(spec)
    machine = load_machine(artifact)
    results = static_checks(spec, artifact)
    roles = role_of(spec)
    counter = capture_counter(spec, roles)
    trusted = {name: True for name in spec["inputs"]}
    # Only inputs the capture guard actually reads can be falsified to force a rejection.
    capture_inputs = sorted(
        r.removeprefix("input.") for r in references(
            next((t["guard"] for t in spec["transitions"] if t["event"] == roles.get("capture")), True))
        if r.startswith("input.")
    )

    def case(name, function, needs=("start", "capture")):
        missing = [role for role in needs if role not in roles]
        if missing:
            results.append({"name": name, "group": "dynamic", "verdict": "SKIP",
                            "reason": f"Đặc tả không có sự kiện đóng vai trò: {', '.join(missing)}"})
            return
        try:
            function()
            results.append({"name": name, "group": "dynamic", "verdict": "PASS"})
        except (AssertionError, ValueError, KeyError) as error:
            results.append({"name": name, "group": "dynamic", "verdict": "FAIL",
                            "reason": str(error) or name})

    def scenario(events):
        monitor = machine["new_monitor"]()
        reports = [monitor.process(event_id, event, inputs) for event_id, event, inputs in events]
        return monitor, reports

    def happy():
        monitor, reports = scenario([("1", roles["start"], {}), ("2", roles["capture"], trusted),
                                     ("3", roles["ship"], trusted)])
        assert all(r["verdict"] == "ACCEPTED" for r in reports), "Luồng thành công bị từ chối"
        assert monitor.state["shipped"], "Đơn không được đánh dấu đã giao"
        if counter:
            assert monitor.state[counter] > 0, f"{counter} không tăng sau khi thu tiền"

    def unpaid():
        state = machine["initial_state"](spec)
        try:
            updated = machine["transition"](state, roles["ship"], trusted)
        except machine["TransitionError"]:
            return
        assert not updated["shipped"], "Bộ máy thô cho giao hàng khi chưa thanh toán"

    def duplicate():
        monitor, reports = scenario([("1", roles["start"], {}), ("2", roles["capture"], trusted),
                                     ("2", roles["capture"], trusted)])
        assert reports[-1]["verdict"] == "DUPLICATE", "Sự kiện trùng không bị nhận ra"
        if counter:
            before = reports[1]["after"][counter]
            assert monitor.state[counter] == before, "Webhook trùng làm thay đổi số tiền đã thu"

    def replayed_id():
        tampered = dict(trusted, **{capture_inputs[0]: False})
        _, reports = scenario([("1", roles["start"], {}), ("2", roles["capture"], trusted),
                               ("2", roles["capture"], tampered)])
        assert reports[-1]["verdict"] == "REJECTED", "ID sự kiện được dùng lại với nội dung khác vẫn lọt"

    def timeout():
        _, reports = scenario([("1", roles["start"], {}), ("2", roles["timeout"], trusted),
                               ("3", roles["capture"], trusted)])
        assert reports[1]["after"]["status"].upper() in UNCERTAIN, "Timeout không dẫn tới trạng thái chờ xác minh"
        assert reports[-1]["verdict"] == "ACCEPTED", "Xác nhận đến muộn bị từ chối"

    def bad_input(field):
        _, reports = scenario([("1", roles["start"], {}),
                               ("2", roles["capture"], dict(trusted, **{field: False}))])
        assert reports[-1]["verdict"] == "REJECTED", f"Chấp nhận xác nhận sai {field}"

    def refund_bounded():
        _, reports = scenario([("1", roles["start"], {}), ("2", roles["capture"], trusted),
                               ("3", roles["refund"], trusted), ("4", roles["refund"], trusted)])
        assert reports[2]["verdict"] == "ACCEPTED", "Hoàn tiền hợp lệ bị từ chối"
        assert reports[3]["verdict"] == "REJECTED", "Hoàn tiền lần hai vẫn được chấp nhận"

    def refund_blocks_shipping():
        _, reports = scenario([("1", roles["start"], {}), ("2", roles["capture"], trusted),
                               ("3", roles["refund"], trusted), ("4", roles["ship"], trusted)])
        assert reports[-1]["verdict"] == "REJECTED", "Vẫn giao hàng được sau khi đã hoàn toàn bộ tiền"

    case("Thanh toán thành công rồi giao hàng", happy, ("start", "capture", "ship"))
    case("Từ chối giao hàng khi chưa thu tiền", unpaid, ("ship",))
    case("Webhook trùng không thu tiền thêm", duplicate)
    case("Dùng lại ID với nội dung khác bị từ chối", replayed_id)
    case("Timeout rồi xác nhận đến muộn", timeout, ("start", "capture", "timeout"))
    for field in capture_inputs:
        case(f"Từ chối khi {field} không đạt", lambda field=field: bad_input(field))
    case("Không hoàn tiền quá số đã thu", refund_bounded, ("start", "capture", "refund"))
    case("Không giao hàng sau khi đã hoàn tiền", refund_blocks_shipping,
         ("start", "capture", "refund", "ship"))
    return {"spec_hash": artifact["spec_hash"], "results": results,
            "elapsed_ms": round((time.monotonic() - started) * 1000),
            "scope": "Phân tích tĩnh mã sinh và đặc tả + kịch bản nghiệp vụ; không phải SAST toàn diện"}
