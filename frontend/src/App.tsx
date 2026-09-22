import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowRight, Braces, Check, ChevronRight, Code2, Download, FileJson, FlaskConical, GitBranch, Info, Layers, ListChecks, LoaderCircle, Menu, Moon, Play, Plus, Save, Scale, ShieldCheck, SlidersHorizontal, Sun, Undo2, X } from 'lucide-react';
import { api } from './api';
import { Badge, Button, Code, Empty, expression, Modal, Panel, StateValues } from './components';
import { ExpressionEditor } from './ExpressionEditor';
import { GraphView } from './GraphView';
import type { Advisory, Artifact, Coverage, Graph, Property, Run, Severity, Spec, State, TestResult, Trace, Verification } from './types';

type Page = 'model' | 'spec' | 'constraints' | 'verify' | 'code' | 'lab' | 'tests' | 'advisory';
const pages = [
  {id: 'spec', name: 'Đặc tả chức năng', icon: SlidersHorizontal, step: '01'},
  {id: 'constraints', name: 'Ràng buộc', icon: Scale, step: '02'},
  {id: 'model', name: 'Mô hình Kripke', icon: GitBranch, step: '03'},
  {id: 'verify', name: 'Kiểm chứng Z3', icon: ShieldCheck, step: '04'},
  {id: 'code', name: 'Sinh mã Python', icon: Code2, step: '05'},
  {id: 'lab', name: 'Phòng mô phỏng', icon: Activity, step: '06'},
  {id: 'tests', name: 'Kiểm thử', icon: FlaskConical, step: '07'},
  {id: 'advisory', name: 'Gợi ý triển khai', icon: ListChecks, step: '08'},
] as const;
const trusted = {provider_verified: true, amount_matches: true, currency_matches: true};
const titles: Record<Page, [string, string]> = {
  model: ['Nhìn thấy mọi bước chuyển.', 'Khám phá trạng thái có thể đạt tới từ đặc tả thanh toán.'],
  spec: ['Bắt đầu bằng một đặc tả rõ ràng.', 'Biến, sự kiện và tham số là nguồn chung cho kiểm chứng và mã sinh.'],
  constraints: ['Viết ra điều không bao giờ được xảy ra.', 'Guard quyết định khi nào một sự kiện được phép; bất biến là điều luôn phải đúng ở mọi trạng thái.'],
  verify: ['Tìm lỗi trước khi thực thi.', 'Z3 tìm đường chạy vi phạm thuộc tính an toàn trong giới hạn k bước.'],
  code: ['Từ mô hình đến mã chạy được.', 'Sinh bộ máy trạng thái, monitor và ca kiểm thử Python độc lập.'],
  lab: ['Đặt thanh toán vào tình huống khó.', 'Cổng giả lập gửi sự kiện vào chính bộ máy Python được sinh.'],
  tests: ['Kiểm tra cả quy tắc lẫn hành vi.', 'Phân tích tĩnh mã sinh và đặc tả, rồi chạy kịch bản nghiệp vụ độc lập.'],
  advisory: ['Từ mô hình đến hệ thống thật.', 'Những gì mô hình đã bảo đảm, và những gì vẫn phải tự làm khi triển khai thanh toán.'],
};
const severityLabel: Record<Severity, string> = {critical: 'Nghiêm trọng', high: 'Cao', medium: 'Trung bình', low: 'Thấp'};
const coverageLabel: Record<Coverage, string> = {
  MODELED: 'Mô hình đã ràng buộc', PARTIAL: 'Mới bao phủ một phần',
  MISSING: 'Mô hình còn thiếu', OUTSIDE_MODEL: 'Ngoài phạm vi mô hình',
};
function tone(verdict: string): 'danger'|'strong'|'neutral' {
  return ['VIOLATED','FAIL','BLOCKED','REJECTED'].includes(verdict) ? 'danger' : ['BOUNDED_SAFE','PASS','ACCEPTED'].includes(verdict) ? 'strong' : 'neutral';
}
function verdictLabel(verdict: string) {
  return ({BOUNDED_SAFE: 'Không tìm thấy lỗi', VIOLATED: 'Có vi phạm', UNKNOWN: 'Chưa kết luận', ACCEPTED: 'Đã áp dụng', REJECTED: 'Từ chối', BLOCKED: 'Đã chặn', DUPLICATE: 'Bỏ qua bản trùng', PASS: 'Đạt', FAIL: 'Không đạt', SKIP: 'Bỏ qua'} as Record<string,string>)[verdict] || verdict;
}
function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function App() {
  const [page, setPage] = useState<Page>('model');
  const [spec, setSpec] = useState<Spec | null>(null);
  const [savedHash, setSavedHash] = useState('');
  const [savedJson, setSavedJson] = useState('');
  const [graph, setGraph] = useState<Graph | null>(null);
  const [selected, setSelected] = useState(0);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [trace, setTrace] = useState<Trace[] | undefined>();
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [file, setFile] = useState('payment_machine.py');
  const [tests, setTests] = useState<TestResult | null>(null);
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [rules, setRules] = useState<Spec | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [bound, setBound] = useState(12);
  const [enforce, setEnforce] = useState(true);
  const [busy, setBusy] = useState('');
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editor, setEditor] = useState(false);
  const [draft, setDraft] = useState('');
  const [mobileMenu, setMobileMenu] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('atpm-theme') || 'light');
  const [customEvent, setCustomEvent] = useState('start');
  const [customInputs, setCustomInputs] = useState<State>({});
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  useEffect(() => {document.documentElement.classList.toggle('dark', theme === 'dark'); localStorage.setItem('atpm-theme', theme);}, [theme]);
  async function action(label: string, task: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(label); setError(''); setNotice('');
    try {await task();} catch (e) {setError(e instanceof Error ? e.message : 'Có lỗi xảy ra');}
    finally {busyRef.current = false; setBusy('');}
  }
  async function installSpec(next: Spec) {
    const nextGraph = await api<Graph>('/graph', {spec: next});
    setSpec(next); setGraph(nextGraph); setSelected(0); setVerification(null); setTrace(undefined); setArtifact(null); setTests(null);
    setAdvisory(null); setRules(structuredClone(next));
    setCustomEvent(next.transitions[0].event); setCustomInputs(Object.fromEntries(Object.entries(next.inputs).map(([name,v]) => [name, v.initial])));
  }
  const initialize = () => action('Đang tải dự án', async () => {
    const data = await api<{spec: Spec; spec_hash: string}>('/spec');
    await installSpec(data.spec); setSavedHash(data.spec_hash); setSavedJson(JSON.stringify(data.spec));
    const runId = localStorage.getItem('atpm-run');
    if (runId) {
      try {setRun(await api<Run>(`/runs/${runId}`));}
      catch {localStorage.removeItem('atpm-run');}
    }
  });
  useEffect(() => {void initialize();}, []);
  const dirty = spec && JSON.stringify(spec) !== savedJson;
  const revision = graph?.spec_hash.slice(0, 8) || '—';
  const nav = (next: Page) => {setPage(next); setMobileMenu(false);};
  async function createRun() {
    const next = await api<Run>('/runs', {spec, enforce});
    setRun(next); localStorage.setItem('atpm-run', next.id); setExpandedEvent(null); return next;
  }
  async function sendEvent(current: Run, event: string, inputs: State = {}, eventId?: string) {
    const updated = await api<Run>(`/runs/${current.id}/events`, {event, inputs, event_id: eventId || crypto.randomUUID()});
    setRun(updated); return updated;
  }
  async function scenario(name: string) {
    let current = await createRun();
    if (name === 'unpaid') {await sendEvent(current, 'ship'); return;}
    current = await sendEvent(current, 'start');
    if (name === 'timeout') current = await sendEvent(current, 'timeout');
    if (name === 'forged') {await sendEvent(current, 'confirm', {...trusted, provider_verified: false}); return;}
    const id = crypto.randomUUID();
    current = await sendEvent(current, 'confirm', trusted, id);
    if (name === 'duplicate') await sendEvent(current, 'confirm', trusted, id);
    else await sendEvent(current, 'ship');
  }

  // Constraint edits stay in a local draft so the graph is recomputed once, on apply.
  const rulesDirty = !!rules && !!spec && JSON.stringify(rules) !== JSON.stringify(spec);
  function editRules(update: (draft: Spec) => void) {
    setRules(current => {
      if (!current) return current;
      const next = structuredClone(current);
      update(next);
      return next;
    });
  }
  function freeInvariantId(draft: Spec) {
    let index = draft.properties.length + 1;
    while (draft.properties.some(p => p.id === `invariant_${index}`)) index += 1;
    return `invariant_${index}`;
  }
  const runAdvisory = () => action('Đang lập gợi ý triển khai', async () => {
    setAdvisory(await api<Advisory>('/advisory', {spec, verification, tests}));
  });

  return <div className="app-layout">
    {mobileMenu && <button className="sidebar-scrim" aria-label="Đóng điều hướng" onClick={() => setMobileMenu(false)}/>}
    <aside className={`sidebar ${mobileMenu ? 'open' : ''}`}>
      <a href="#" className="brand" onClick={e => {e.preventDefault(); nav('model');}}><span className="brand-icon"><Layers size={23}/></span><span>Proof Lab<small>An toàn phần mềm</small></span></a>
      <div className="workspace"><span className="workspace-icon"><Braces size={18}/></span><span>Payment workspace<small>Dự án cục bộ</small></span><ChevronRight size={15}/></div>
      <div className="nav-caption">Quy trình phát triển</div>
      <nav aria-label="Quy trình phát triển">{pages.map(item => <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} aria-current={page === item.id ? 'page' : undefined} onClick={() => nav(item.id)}><item.icon size={18}/><span>{item.name}</span><small>{item.step}</small></button>)}</nav>
      <div className="sidebar-guide"><GitBranch size={20}/><p>Một đặc tả.<br/>Từ kiểm chứng đến thực thi.</p><span>Mọi kết quả đều gắn với phiên bản mô hình.</span></div>
      <div className="sidebar-footer"><span><span className="dot"/> Local sandbox</span><button className="icon-button" onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')} aria-label="Đổi giao diện sáng tối">{theme === 'light' ? <Moon size={17}/> : <Sun size={17}/>}</button></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-toggle" aria-label="Mở điều hướng" onClick={() => setMobileMenu(true)}><Menu size={20}/></button><span>Workspace</span><ChevronRight size={14}/><strong>{pages.find(p => p.id === page)?.name}</strong></div><div className="topbar-actions"><Badge>{dirty ? 'Chưa lưu' : 'Đã lưu'}</Badge><Button disabled={!spec || !!busy || !dirty} onClick={() => action('Đang lưu đặc tả', async () => {
        const data = await api<{spec: Spec; spec_hash: string}>('/spec', {spec, expected_hash: savedHash}, 'PUT');
        setSpec(data.spec); setSavedHash(data.spec_hash); setSavedJson(JSON.stringify(data.spec)); setNotice('Đã lưu đặc tả vào SQLite.');
      })}><Save size={15}/><span>Lưu đặc tả</span></Button></div></header>
      <div className="page-scroll">
        <div className="page-content">
          <div className="project-line"><span className="project-dot"/><span>{spec?.name || 'Payment Proof Lab'}</span><Badge>Python · Z3</Badge><code>#{revision}</code></div>
          <div className="page-heading"><div><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div>{spec && <Button onClick={() => {setDraft(JSON.stringify(spec, null, 2)); setEditor(true);}} disabled={!!busy}><FileJson size={16}/> Sửa đặc tả JSON</Button>}</div>
          {error && <div className="alert danger" role="alert"><Info size={18}/><span>{error}</span><button className="icon-button" aria-label="Đóng lỗi" onClick={() => setError('')}><X size={16}/></button></div>}
          {notice && <div className="alert" role="status"><Check size={18}/><span>{notice}</span></div>}
          {busy && <div className="busy-bar" role="status"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
          {!spec || !graph ? <Panel><Empty title={error ? 'Chưa tải được dự án' : 'Đang mở không gian làm việc'}>Backend cần chạy tại cổng 8010.</Empty><div className="center-action"><Button onClick={initialize} disabled={!!busy}>Thử tải lại</Button></div></Panel> : <>
            {page === 'model' && <>
              <div className="metric-strip"><div><span>Trạng thái có thể đạt tới</span><strong>{graph.nodes.length.toString().padStart(2,'0')}</strong></div><div><span>Sự kiện được định nghĩa</span><strong>{spec.transitions.length.toString().padStart(2,'0')}</strong></div><div><span>Thuộc tính an toàn</span><strong>{spec.properties.length.toString().padStart(2,'0')}</strong></div><div><span>Không gian trạng thái</span><strong>{Object.values(spec.variables).reduce((a,v) => a*v.values.length,1)}<small> tổ hợp</small></strong></div></div>
              <div className="section-title"><div><h2>Đồ thị trạng thái</h2><span>Kripke K = (S, S₀, R, L)</span></div><div className="button-group"><Button disabled={!!busy} onClick={() => action('Nạp mẫu an toàn', async () => {const data = await api<{spec: Spec}>('/examples/safe'); await installSpec(data.spec);})}>Mẫu an toàn</Button><Button disabled={!!busy} onClick={() => action('Nạp mẫu hoàn tiền', async () => {const data = await api<{spec: Spec}>('/examples/refund'); await installSpec(data.spec); setNotice('Đã nạp mẫu mở rộng: thu một phần, hoàn tiền từng phần và đối soát với cổng.');})}>Mẫu hoàn tiền</Button><Button disabled={!!busy} onClick={() => action('Nạp mẫu có lỗi', async () => {const data = await api<{spec: Spec}>('/examples/unsafe'); await installSpec(data.spec); setNotice('Đã nạp lỗi chủ đích: cho giao hàng khi chưa thanh toán. Chạy Z3 để tìm phản ví dụ.');})}>Thử mẫu có lỗi</Button></div></div>
              <Panel className="graph-panel"><GraphView graph={graph} selected={selected} onSelect={setSelected} trace={trace}/></Panel>
              <div className="two-columns"><Panel><div className="panel-heading"><h3>Trạng thái s{selected}</h3><Badge tone={graph.nodes[selected]?.violations.length ? 'danger' : 'neutral'}>{graph.nodes[selected]?.violations.length ? 'Vi phạm' : 'Giá trị biến'}</Badge></div><StateValues state={graph.nodes[selected]?.state || {}}/></Panel><Panel><div className="panel-heading"><h3>Điều gì cần được bảo đảm?</h3><ShieldCheck size={18}/></div><div className="property-list">{spec.properties.map(p => <div key={p.id}><Check size={15}/><span>{p.label}</span></div>)}</div><button className="text-button" onClick={() => nav('verify')}>Kiểm chứng các thuộc tính <ArrowRight size={16}/></button></Panel></div>
              <div className="footnote"><Info size={15}/><span>Mỗi nút là một tổ hợp giá trị biến, không chỉ là tên trạng thái thanh toán. Đồ thị được tính từ đặc tả hiện tại.</span></div>
            </>}

            {page === 'spec' && <>
              <Panel><div className="panel-heading"><h2>Phạm vi chức năng</h2><Badge>Đặc tả thực thi</Badge></div><p className="body-copy">{spec.description}</p><label className="field-label">Tên chức năng<input value={spec.name} maxLength={100} disabled={!!busy} onChange={e => setSpec({...spec, name: e.target.value})} onBlur={() => {if(spec.name) void action('Cập nhật mô hình', () => installSpec(spec));}}/></label></Panel>
              <div className="section-title"><h2>Biến trạng thái</h2><span>Miền hữu hạn · {Object.keys(spec.variables).length} biến</span></div>
              <Panel className="table-panel"><div className="table-scroll"><table><thead><tr><th>Biến</th><th>Ý nghĩa</th><th>Miền giá trị</th><th>Khởi đầu</th></tr></thead><tbody>{Object.entries(spec.variables).map(([name, v]) => <tr key={name}><td><code>{name}</code></td><td>{v.label}</td><td><div className="value-chips">{v.values.map(value => <Badge key={String(value)}>{String(value)}</Badge>)}</div></td><td><select aria-label={`Giá trị khởi đầu ${name}`} value={JSON.stringify(v.initial)} disabled={!!busy} onChange={e => action('Cập nhật mô hình', () => installSpec({...spec, variables: {...spec.variables, [name]: {...v, initial: JSON.parse(e.target.value)}}}))}>{v.values.map(value => <option key={String(value)} value={JSON.stringify(value)}>{String(value)}</option>)}</select></td></tr>)}</tbody></table></div></Panel>
              <div className="section-title"><h2>Tham số sự kiện</h2><span>Giá trị sau bước xác thực phía máy chủ</span></div><Panel className="table-panel"><div className="table-scroll"><table><thead><tr><th>Tham số</th><th>Ý nghĩa</th><th>Mặc định</th></tr></thead><tbody>{Object.entries(spec.inputs).map(([name,v]) => <tr key={name}><td><code>{name}</code></td><td>{v.label}</td><td>{String(v.initial)}</td></tr>)}</tbody></table></div></Panel>
              <div className="section-title"><h2>Quan hệ chuyển trạng thái</h2><Button disabled={!!busy} onClick={() => {setDraft(JSON.stringify(spec,null,2)); setEditor(true);}}><Braces size={15}/> Chỉnh sửa quy tắc</Button></div>
              <div className="transition-list">{spec.transitions.map(t => <Panel key={t.event}><div className="panel-heading"><h3>{t.label}</h3><code>{t.event}</code></div><div className="transition-route"><span>{t.from_states.join(' / ')}</span><ArrowRight size={16}/><strong>{t.to_state}</strong></div><div className="rule-line"><span>Điều kiện</span><code>{expression(t.guard)}</code></div><div className="rule-line"><span>Cập nhật</span><code>{Object.entries(t.effects).map(([k,v]) => `${k} := ${expression(v)}`).join('; ') || 'Giữ nguyên các biến khác'}</code></div></Panel>)}</div>
              <Panel><div className="panel-heading"><h2>Giả định và giới hạn mô hình</h2><Info size={18}/></div><ul className="assumptions">{spec.assumptions.map(a => <li key={a}>{a}</li>)}</ul></Panel>
            </>}

            {page === 'constraints' && rules && <>
              <Panel className="run-toolbar"><div><h2>Guard và bất biến</h2><p>Sửa điều kiện bằng biểu mẫu; không cần viết JSON. Thay đổi chỉ được áp dụng khi bạn bấm kiểm tra.</p></div><Badge tone={rulesDirty ? 'danger' : 'neutral'}>{rulesDirty ? 'Có thay đổi chưa áp dụng' : 'Khớp với mô hình hiện tại'}</Badge><div className="button-group"><Button disabled={!!busy || !rulesDirty} onClick={() => setRules(structuredClone(spec))}><Undo2 size={15}/> Hoàn tác</Button><Button variant="primary" disabled={!!busy || !rulesDirty} onClick={() => action('Kiểm tra ràng buộc', async () => {await installSpec(rules); setNotice('Đã áp dụng ràng buộc mới. Chạy lại kiểm chứng Z3 để xem kết quả.');})}><Check size={15}/> Kiểm tra và áp dụng</Button></div></Panel>
              <div className="notice"><Info size={17}/><span>Bất biến phải đúng ở <strong>mọi</strong> trạng thái đạt tới được; đó là thứ Z3 cố gắng bác bỏ. Guard chỉ quyết định một sự kiện có được phép xảy ra hay không.</span></div>

              <div className="section-title"><div><h2>Bất biến an toàn</h2><span>{rules.properties.length}/8 thuộc tính · kiểu boolean, không đọc tham số sự kiện</span></div><Button disabled={!!busy || rules.properties.length >= 8} onClick={() => editRules(draft => {draft.properties.push({id: freeInvariantId(draft), label: 'Bất biến mới', expression: {implies: [true, true]}} as Property);})}><Plus size={15}/> Thêm bất biến</Button></div>
              {rules.properties.map((property, index) => <Panel key={index} className="rule-editor">
                <div className="panel-heading"><label className="field-label rule-name">Mô tả bằng lời<input value={property.label} maxLength={160} disabled={!!busy} onChange={e => editRules(draft => {draft.properties[index].label = e.target.value;})}/></label><label className="field-label rule-id">Định danh<input value={property.id} maxLength={40} disabled={!!busy} pattern="[a-z][a-z0-9_]*" onChange={e => editRules(draft => {draft.properties[index].id = e.target.value;})}/></label><Button variant="ghost" disabled={!!busy || rules.properties.length <= 1} onClick={() => editRules(draft => {draft.properties.splice(index, 1);})}><X size={15}/> Xóa</Button></div>
                <code className="formula">AG {expression(property.expression)}</code>
                <ExpressionEditor expr={property.expression} spec={rules} allowInputs={false} disabled={!!busy} onChange={next => editRules(draft => {draft.properties[index].expression = next;})}/>
              </Panel>)}

              <div className="section-title"><div><h2>Điều kiện của từng sự kiện</h2><span>Guard đọc được cả biến trạng thái và tham số sự kiện</span></div></div>
              {rules.transitions.map((transition, index) => <Panel key={transition.event} className="rule-editor">
                <div className="panel-heading"><div><h3>{transition.label}</h3><div className="transition-route"><span>{transition.from_states.join(' / ')}</span><ArrowRight size={14}/><strong>{transition.to_state}</strong></div></div><code>{transition.event}</code></div>
                <code className="formula">{expression(transition.guard)}</code>
                <ExpressionEditor expr={transition.guard} spec={rules} allowInputs disabled={!!busy} onChange={next => editRules(draft => {draft.transitions[index].guard = next;})}/>
              </Panel>)}
              <div className="footnote"><Info size={15}/><span>Kiểu được kiểm tra ở máy chủ khi áp dụng: so sánh hai kiểu khác nhau, guard không phải boolean hay bất biến đọc tham số sự kiện đều bị từ chối kèm lý do.</span></div>
            </>}

            {page === 'verify' && <>
              <Panel className="run-toolbar"><div><h2>Bounded model checking</h2><p>Tìm phản ví dụ ngắn nhất trong phạm vi 0…k bước.</p></div><label className="inline-field">Giới hạn k<input aria-label="Giới hạn bước k" type="number" min={0} max={30} value={bound} onChange={e => setBound(Number(e.target.value))}/></label><Button variant="primary" disabled={!!busy || !Number.isInteger(bound) || bound < 0 || bound > 30} onClick={() => action('Z3 đang kiểm chứng', async () => {setTrace(undefined); setVerification(await api<Verification>('/verify', {spec, bound}));})}><Play size={16}/> Chạy kiểm chứng</Button></Panel>
              <div className="notice"><Info size={17}/><span>“Không tìm thấy lỗi” chỉ áp dụng trong giới hạn đã kiểm tra. Đây không phải chứng minh vô hạn hoặc kiểm chứng liveness.</span></div>
              {verification ? <><div className="section-title"><h2>Kết quả kiểm chứng</h2><span>{verification.solver} · {verification.elapsed_ms} ms · k = {verification.bound} · #{verification.spec_hash.slice(0,8)}</span></div><div className="results-list">{verification.results.map(result => <Panel key={result.id}><div className="result-heading"><span className={`result-symbol ${result.verdict === 'VIOLATED' ? 'danger' : ''}`}>{result.verdict === 'VIOLATED' ? <X size={20}/> : result.verdict === 'BOUNDED_SAFE' ? <Check size={20}/> : <Info size={20}/>}</span><div><h3>{result.label}</h3><code>{result.id}</code></div><Badge tone={tone(result.verdict)}>{verdictLabel(result.verdict)}</Badge></div><code className="formula">AG {expression(spec.properties.find(p => p.id === result.id)!.expression)}</code>{result.trace ? <div className="counterexample"><div className="section-title"><h4>Phản ví dụ · {result.depth} bước</h4><Button onClick={() => {setTrace(result.trace); nav('model');}}>Xem trên đồ thị <ArrowRight size={14}/></Button></div><div className="trace-steps">{result.trace.map(t => <div key={t.step}><span className="step-number">{t.step}</span><div><strong>{t.event === 'initial' ? 'Khởi đầu' : t.event}</strong><code>{Object.entries(t.state).map(([k,v]) => `${k}=${v}`).join(' · ')}</code>{Object.keys(t.inputs).length > 0 && <small>Input: {JSON.stringify(t.inputs)}</small>}</div></div>)}</div></div> : <p className="result-note">{result.reason || `Không có trạng thái vi phạm trên các đường chạy dài tối đa ${result.checked_depth} bước.`}</p>}</Panel>)}</div></> : <Panel><Empty title="Sẵn sàng tìm phản ví dụ">Chọn giới hạn bước rồi chạy Z3. Kết quả được tính từ đặc tả, không phải dữ liệu minh họa.</Empty></Panel>}
            </>}

            {page === 'code' && <>
              <Panel className="run-toolbar"><div><h2>Python 3.11+</h2><p>Mã độc lập, không cần Z3 khi triển khai bộ máy trạng thái.</p></div><Button variant="primary" disabled={!!busy} onClick={() => action('Đang sinh mã Python', async () => {setArtifact(await api<Artifact>('/generate', {spec}));})}><Code2 size={16}/> Sinh mã Python</Button></Panel>
              <div className="notice"><Info size={17}/><span>Sinh mã không đồng nghĩa mã đã được chứng nhận an toàn. Kết nối cổng, xác thực webhook và giao dịch DB cần kiểm thử tích hợp riêng.</span></div>
              {artifact ? <Panel className="source-panel"><div className="source-header"><div><Badge tone="strong">#{artifact.spec_hash.slice(0,8)}</Badge><span>{artifact.vector_count} ca chuyển trạng thái{!artifact.vectors_complete && ' (giới hạn khám phá)'}</span></div><Button disabled={!!busy} onClick={() => action('Đang tạo gói tải xuống', async () => {const response = await fetch('/api/download', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({spec})}); if(!response.ok) throw new Error('Không thể tạo gói mã'); downloadBlob(await response.blob(), `payment-${revision}.zip`);})}><Download size={15}/> Tải gói ZIP</Button></div><div className="file-tabs" role="tablist" aria-label="Các file được sinh">{Object.keys(artifact.files).map(name => <button role="tab" aria-selected={file === name} key={name} onClick={() => setFile(name)} className={file === name ? 'active' : ''}>{name}</button>)}</div><Code source={artifact.files[file]}/></Panel> : <Panel><Empty title="Mã được sinh từ phiên bản hiện tại">Gói đầu ra gồm payment_machine.py, payment_monitor.py, test_payment_generated.py và đặc tả gốc.</Empty></Panel>}
              <div className="two-columns"><Panel><h3>Bộ máy chuyển trạng thái</h3><p className="body-copy">Hàm thuần nhận trạng thái và sự kiện, kiểm tra guard, rồi trả trạng thái mới. Mọi phép gán đọc cùng trạng thái trước đó.</p></Panel><Panel><h3>Giám sát khi chạy</h3><p className="body-copy">Monitor kiểm tra bất biến và ID sự kiện. Backend chịu trách nhiệm lưu trạng thái, ID đã xử lý và nhật ký trong một transaction.</p></Panel></div>
            </>}

            {page === 'lab' && <>
              <Panel className="run-toolbar"><div><h2>Thanh toán giả lập</h2><p>Không có giao dịch hay tiền thật. Phiên lưu bền vững trong SQLite.</p></div><label className="check-label"><input type="checkbox" checked={enforce} onChange={e => setEnforce(e.target.checked)}/> Chặn vi phạm ở phiên mới</label><Button variant="primary" disabled={!!busy} onClick={() => action('Tạo phiên từ mã sinh', async () => {await createRun();})}><Plus size={16}/> Phiên mới</Button></Panel>
              {run && run.spec_hash !== graph.spec_hash && <div className="notice"><Info size={17}/>Phiên đang chạy dùng đặc tả #{run.spec_hash.slice(0,8)}. Tạo phiên mới để sử dụng đặc tả hiện tại.</div>}
              <div className="scenario-strip">{[{id:'happy',title:'Thành công',desc:'Thu tiền → giao hàng'},{id:'timeout',title:'Timeout',desc:'Xác nhận đến muộn'},{id:'duplicate',title:'Webhook trùng',desc:'Cùng một event ID'},{id:'forged',title:'Webhook giả',desc:'Nguồn chưa xác thực'},{id:'unpaid',title:'Giao hàng sớm',desc:'Chưa có thanh toán'}].map(s => <button key={s.id} disabled={!!busy} onClick={() => action(`Chạy kịch bản ${s.title.toLowerCase()}`, () => scenario(s.id))}><Play size={15}/><strong>{s.title}</strong><small>{s.desc}</small></button>)}</div><p className="subtle">Mỗi kịch bản tạo một phiên mới với đặc tả hiện tại.</p>
              {run ? <div className="lab-grid"><Panel className="order-panel"><div className="panel-heading"><h3>Đơn hàng mô phỏng</h3><Badge tone="strong">{String(run.state.status)}</Badge></div><div className="order-product"><span className="product-art"><Layers size={35}/></span><div><strong>Đơn hàng thử nghiệm</strong><small>Thanh toán toàn bộ · VND</small></div></div><div className="order-total"><span>Giá trị minh họa</span><strong>100.000 ₫</strong></div><p className="subtle">Số tiền được trừu tượng hóa bằng amount_matches trong mô hình.</p><StateValues state={run.state}/><div className="monitor-mode"><ShieldCheck size={17}/>{run.enforce ? 'Monitor chặn trước cập nhật' : 'Chỉ quan sát, có thể ghi nhận vi phạm'}</div><small className="revision-line">Phiên {run.id.slice(0,8)} · mã #{run.spec_hash.slice(0,8)}</small></Panel><Panel className="event-panel"><div className="panel-heading"><h3>Dòng sự kiện</h3><Badge>{run.events.length} sự kiện</Badge></div>{run.events.length ? <div className="event-list">{run.events.map((event, index) => <div className="event-entry" key={`${event.event_id}-${index}`}><button className="event-summary" onClick={() => setExpandedEvent(expandedEvent === index ? null : index)} aria-expanded={expandedEvent === index}><span className="event-index">{index+1}</span><div><strong>{event.event}</strong><small>{event.reason}</small></div><Badge tone={tone(event.verdict)}>{verdictLabel(event.verdict)}</Badge></button>{expandedEvent === index && <div className="event-detail"><code>ID: {event.event_id}</code><p>{event.timestamp} UTC</p><StateValues state={event.candidate || event.after}/>{event.violations.length > 0 && <p className="error-text">{event.violations.join(', ')}</p>}</div>}</div>)}</div> : <Empty title="Chưa có sự kiện">Gửi một sự kiện bên dưới hoặc chạy kịch bản có sẵn.</Empty>}</Panel></div> : <Panel><Empty title="Bắt đầu một lần thanh toán">Tạo phiên hoặc chọn một kịch bản để chạy mã được sinh và quan sát monitor.</Empty></Panel>}
              {run && run.spec_hash === graph.spec_hash && <Panel><div className="panel-heading"><h3>Gửi sự kiện thủ công</h3><Badge>Cổng giả lập</Badge></div><div className="manual-events"><label className="field-label">Sự kiện<select value={customEvent} onChange={e => setCustomEvent(e.target.value)}>{spec.transitions.map(t => <option key={t.event} value={t.event}>{t.event} — {t.label}</option>)}</select></label>{Object.entries(spec.inputs).map(([name,v]) => <label className="field-label" key={name}>{name}<select value={JSON.stringify(customInputs[name] ?? v.initial)} onChange={e => setCustomInputs({...customInputs, [name]: JSON.parse(e.target.value)})}>{v.values.map(value => <option key={String(value)} value={JSON.stringify(value)}>{String(value)}</option>)}</select></label>)}<Button disabled={!!busy} onClick={() => action('Đang xử lý sự kiện', async () => {await sendEvent(run, customEvent, customInputs);})}><Play size={15}/> Gửi sự kiện</Button></div>{run.events.some(e => e.verdict === 'ACCEPTED') && <Button disabled={!!busy} onClick={() => action('Gửi lại sự kiện gần nhất', async () => {const last = [...run.events].reverse().find(e => e.verdict === 'ACCEPTED')!; await sendEvent(run, last.event, last.inputs, last.event_id);})}>Gửi lại sự kiện đã áp dụng gần nhất</Button>}</Panel>}
            </>}

            {page === 'tests' && <>
              <Panel className="run-toolbar"><div><h2>Bộ kiểm thử thanh toán</h2><p>Chạy trực tiếp trên artifact Python được sinh từ đặc tả hiện tại.</p></div><Button variant="primary" disabled={!!busy} onClick={() => action('Đang chạy kiểm thử', async () => {setTests(await api<TestResult>('/tests', {spec}));})}><FlaskConical size={16}/> Chạy kiểm thử</Button></Panel>
              {tests ? <><div className="metric-strip"><div><span>Đạt</span><strong>{tests.results.filter(r => r.verdict === 'PASS').length}</strong></div><div><span>Không đạt</span><strong className={tests.results.some(r => r.verdict === 'FAIL') ? 'error-text' : ''}>{tests.results.filter(r => r.verdict === 'FAIL').length}</strong></div><div><span>Bỏ qua</span><strong>{tests.results.filter(r => r.verdict === 'SKIP').length}</strong></div><div><span>Thời gian</span><strong>{tests.elapsed_ms}<small> ms</small></strong></div></div><Panel className="table-panel"><div className="table-scroll"><table><thead><tr><th>Ca kiểm thử</th><th>Loại</th><th>Kết quả</th></tr></thead><tbody>{tests.results.map(test => <tr key={test.name}><td><strong>{test.name}</strong>{test.reason && <small className="table-reason">{test.reason}</small>}</td><td>{test.group === 'static' ? 'Tĩnh · cú pháp' : 'Động · nghiệp vụ'}</td><td><Badge tone={tone(test.verdict)}>{verdictLabel(test.verdict)}</Badge></td></tr>)}</tbody></table></div></Panel><p className="subtle">{tests.scope} · #{tests.spec_hash.slice(0,8)}</p></> : <Panel><Empty title="Chưa chạy kiểm thử trên phiên bản này">Các kịch bản kiểm tra giao hàng sớm, webhook trùng, timeout và dữ liệu xác nhận không hợp lệ.</Empty></Panel>}
              <div className="two-columns"><Panel><h3>Kiểm chứng mô hình</h3><p className="body-copy">Z3 khảo sát các đường chạy của mô hình trong giới hạn k. Kết quả nằm ở màn hình Kiểm chứng Z3.</p><button className="text-button" onClick={() => nav('verify')}>Mở kiểm chứng <ArrowRight size={15}/></button></Panel><Panel><h3>Kiểm thử mã thực thi</h3><p className="body-copy">Các kịch bản nghiệp vụ kiểm tra kết quả cụ thể. Bộ pytest của dự án còn đối chiếu ngữ nghĩa bộ sinh, graph và Z3.</p></Panel></div>
            </>}

            {page === 'advisory' && <>
              <Panel className="run-toolbar"><div><h2>Danh sách kiểm tra khi triển khai</h2><p>Suy ra từ chính đặc tả. Kết quả kiểm chứng và kiểm thử gần nhất, nếu có, được đưa lên đầu danh sách.</p></div><div className="advisory-sources"><span>{verification ? `Đã có kết quả Z3 #${verification.spec_hash.slice(0,8)}` : 'Chưa chạy kiểm chứng Z3'}</span><span>{tests ? `Đã có kết quả kiểm thử #${tests.spec_hash.slice(0,8)}` : 'Chưa chạy kiểm thử'}</span></div><Button variant="primary" disabled={!!busy} onClick={runAdvisory}><ListChecks size={16}/> Lập gợi ý</Button></Panel>
              <div className="notice"><Info size={17}/><span>Gợi ý này không thay thế đánh giá bảo mật hay kiểm toán PCI DSS. Mục “Ngoài phạm vi mô hình” là những rủi ro mà bộ kiểm chứng <strong>không</strong> kiểm được.</span></div>
              {advisory ? <>
                <div className="metric-strip">{(['critical','high','medium','low'] as Severity[]).map(level => <div key={level}><span>{severityLabel[level]}</span><strong className={level === 'critical' && advisory.severity_counts[level] ? 'error-text' : ''}>{advisory.severity_counts[level].toString().padStart(2,'0')}</strong></div>)}</div>
                <div className="coverage-strip">{(['MODELED','PARTIAL','MISSING','OUTSIDE_MODEL'] as Coverage[]).map(status => <div key={status}><strong>{advisory.coverage_counts[status]}</strong><span>{coverageLabel[status]}</span></div>)}</div>
                <div className="section-title"><div><h2>Khuyến nghị theo mức độ</h2><span>#{advisory.spec_hash.slice(0,8)} · {advisory.items.length} mục</span></div></div>
                <div className="advisory-list">{advisory.items.map(entry => <Panel key={entry.id} className={`advisory-card ${entry.severity}`}>
                  <div className="advisory-head"><div><h3>{entry.title}</h3><code>{entry.id}</code></div><div className="advisory-tags"><Badge tone={entry.severity === 'critical' ? 'danger' : entry.severity === 'high' ? 'strong' : 'neutral'}>{severityLabel[entry.severity]}</Badge><Badge tone={entry.status === 'MODELED' ? 'strong' : entry.status === 'MISSING' ? 'danger' : 'neutral'}>{coverageLabel[entry.status]}</Badge><Badge>{entry.area}</Badge></div></div>
                  <p className="advisory-evidence">{entry.evidence}</p>
                  <ul className="advisory-guidance">{entry.guidance.map(line => <li key={line}>{line}</li>)}</ul>
                </Panel>)}</div>
                <p className="subtle">{advisory.scope}</p>
              </> : <Panel><Empty title="Chưa lập gợi ý cho phiên bản này">Chạy kiểm chứng Z3 và kiểm thử trước để các phát hiện thật được đưa vào danh sách, rồi quay lại đây.</Empty><div className="center-action"><Button variant="primary" disabled={!!busy} onClick={runAdvisory}><ListChecks size={16}/> Lập gợi ý</Button></div></Panel>}
            </>}
          </>}
          <footer className="page-footer"><span>Payment Proof Lab</span><span>Đặc tả → kiểm chứng → thực thi</span></footer>
        </div>
      </div>
    </main>
    {editor && <Modal title="Chỉnh sửa đặc tả JSON" close={() => {if(!busy) setEditor(false);}}><p className="editor-help">Dùng $tên_biến, $input.tên_tham_số và các toán tử eq, ne, le, lt, and, or, not, implies, add, sub. Không hỗ trợ mã Python tùy ý.</p><textarea autoFocus className="json-editor" aria-label="Nội dung đặc tả JSON" spellCheck={false} value={draft} onChange={e => setDraft(e.target.value)}/>{error && <p className="editor-error" role="alert">{error}</p>}<div className="modal-footer"><Button disabled={!!busy} onClick={() => setEditor(false)}>Hủy</Button><Button variant="primary" disabled={!!busy} onClick={() => action('Kiểm tra đặc tả', async () => {const next = JSON.parse(draft) as Spec; await installSpec(next); setEditor(false); setNotice('Đã áp dụng đặc tả. Các kết quả cũ được xóa; lưu để giữ thay đổi sau khi tải lại.');})}><Check size={16}/> Kiểm tra và áp dụng</Button></div></Modal>}
  </div>;
}
