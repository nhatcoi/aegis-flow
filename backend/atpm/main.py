import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import Field

from .advisory import advise
from .formal import explore, verify
from .generation import archive, generate, load_machine
from .specification import Specification, StrictModel, spec_hash
from .storage import ROOT, database, initialize, read_run
from .testing import exercise


@asynccontextmanager
async def lifespan(app):
    initialize()
    yield


app = FastAPI(title="Payment Proof Lab", version="0.1.0", lifespan=lifespan)


def dev_origins():
    """Origins the Vite dev server may run on.

    ATPM_UI_PORT overrides the port; ATPM_UI_ORIGINS replaces the list outright for a
    setup this rule cannot express. Both loopback spellings are accepted because the
    browser sends whichever one is typed into the address bar.
    """
    custom = os.environ.get("ATPM_UI_ORIGINS", "").strip()
    if custom:
        return {origin.strip().rstrip("/") for origin in custom.split(",") if origin.strip()}
    port = os.environ.get("ATPM_UI_PORT", "5173").strip()
    return {f"http://localhost:{port}", f"http://127.0.0.1:{port}"}


@app.middleware("http")
async def local_requests(request: Request, call_next):
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        origin = request.headers.get("origin")
        # Vite's dev proxy retains the browser origin.
        allowed = {str(request.base_url).rstrip("/"), *dev_origins()}
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin không được phép"}, status_code=403)
        if len(await request.body()) > 262144:
            return JSONResponse({"detail": "Đặc tả tối đa 256 KB"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


class SpecRequest(StrictModel):
    spec: Specification


class SaveRequest(SpecRequest):
    expected_hash: str


class VerifyRequest(SpecRequest):
    bound: int = Field(default=12, ge=0, le=30)


class RunRequest(SpecRequest):
    enforce: bool = True


class AdvisoryRequest(SpecRequest):
    # Optional: passing the latest checker and test output promotes findings to critical.
    verification: dict | None = None
    tests: dict | None = None


class EventRequest(StrictModel):
    event_id: str = Field(min_length=1, max_length=100)
    event: str = Field(min_length=1, max_length=40)
    inputs: dict = Field(default_factory=dict, max_length=7)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": "Payment Proof Lab"}


@app.get("/api/spec")
def get_spec():
    with database() as db:
        payload = json.loads(db.execute("SELECT payload FROM project WHERE id=1").fetchone()[0])
    return {"spec": payload, "spec_hash": spec_hash(payload)}


@app.put("/api/spec")
def save_spec(body: SaveRequest):
    spec = body.spec.model_dump()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        current = json.loads(db.execute("SELECT payload FROM project WHERE id=1").fetchone()[0])
        if spec_hash(current) != body.expected_hash:
            raise HTTPException(409, "Đặc tả đã thay đổi ở phiên khác. Tải lại trước khi lưu.")
        db.execute("UPDATE project SET payload=? WHERE id=1", (json.dumps(spec),))
    return {"spec": spec, "spec_hash": spec_hash(spec)}


@app.get("/api/examples/{name}")
def example(name: str):
    if name not in {"safe", "unsafe", "refund"}:
        raise HTTPException(404, "Không tìm thấy mẫu")
    if name == "refund":
        return {"spec": json.loads((ROOT / "specs/payment_refund.json").read_text())}
    spec = json.loads((ROOT / "specs/payment.json").read_text())
    if name == "unsafe":
        spec["name"] = "Thanh toán — mẫu có lỗi"
        ship = next(t for t in spec["transitions"] if t["event"] == "ship")
        ship["from_states"] = spec["variables"]["status"]["values"]
        ship["guard"] = {"not": ["$shipped"]}
        spec["description"] = "Lỗi chủ đích: cho giao hàng từ mọi trạng thái mà không kiểm tra bằng chứng."
    return {"spec": spec}


@app.post("/api/graph")
def graph(body: SpecRequest):
    return explore(body.spec.model_dump())


@app.post("/api/verify")
def check(body: VerifyRequest):
    return verify(body.spec.model_dump(), body.bound)


@app.post("/api/generate")
def code(body: SpecRequest):
    return generate(body.spec.model_dump())


@app.post("/api/download")
def download(body: SpecRequest):
    artifact = generate(body.spec.model_dump())
    return Response(archive(artifact), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="payment-{artifact["spec_hash"][:8]}.zip"'})


@app.post("/api/tests")
def tests(body: SpecRequest):
    return exercise(body.spec.model_dump())


@app.post("/api/advisory")
def advisory(body: AdvisoryRequest):
    return advise(body.spec.model_dump(), body.verification, body.tests)


@app.post("/api/runs")
def create_run(body: RunRequest):
    spec = body.spec.model_dump()
    artifact = generate(spec)
    machine = load_machine(artifact)
    run_id = uuid.uuid4().hex
    with database() as db:
        db.execute("INSERT OR IGNORE INTO artifacts(hash,payload) VALUES(?,?)",
                   (artifact["spec_hash"], json.dumps(artifact)))
        db.execute("INSERT INTO runs(id,spec_hash,state,seen,enforce) VALUES(?,?,?,?,?)",
                   (run_id, artifact["spec_hash"], json.dumps(machine["initial_state"](spec)), "{}", body.enforce))
        return read_run(db, run_id)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with database() as db:
        result = read_run(db, run_id)
    if result is None:
        raise HTTPException(404, "Phiên mô phỏng không tồn tại")
    return result


@app.post("/api/runs/{run_id}/events")
def apply_event(run_id: str, body: EventRequest):
    with database() as db:
        # One atomic transaction includes deduplication, monitor decision, state and audit log.
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Phiên mô phỏng không tồn tại")
        count = db.execute("SELECT COUNT(*) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
        if count >= 200:
            raise HTTPException(409, "Phiên đạt 200 sự kiện. Tạo phiên mới để tiếp tục.")
        artifact = json.loads(db.execute("SELECT payload FROM artifacts WHERE hash=?", (row["spec_hash"],)).fetchone()[0])
        machine = load_machine(artifact)
        monitor = machine["new_monitor"](json.loads(row["state"]), json.loads(row["seen"]))
        report = monitor.process(body.event_id, body.event, body.inputs, enforce=bool(row["enforce"]))
        report.update(event_id=body.event_id, event=body.event, inputs=body.inputs)
        db.execute("UPDATE runs SET state=?, seen=? WHERE id=?",
                   (json.dumps(monitor.state), json.dumps(monitor.seen), run_id))
        db.execute("INSERT INTO events(run_id,payload) VALUES(?,?)", (run_id, json.dumps(report)))
        return read_run(db, run_id)


frontend = ROOT / "frontend/dist"
if frontend.exists():
    app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
