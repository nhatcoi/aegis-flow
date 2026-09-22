import { vi } from 'vitest';
import type { Advisory, Graph, Spec, TestResult, Verification } from './types';

export const spec: Spec = {
  name: 'Thanh toán thử',
  description: 'Mô hình rút gọn dùng cho kiểm thử giao diện.',
  assumptions: ['Sự kiện được xử lý tuần tự theo đơn.'],
  variables: {
    status: {label: 'Trạng thái thanh toán', values: ['CREATED', 'SUCCEEDED'], initial: 'CREATED'},
    shipped: {label: 'Đã yêu cầu giao hàng', values: [false, true], initial: false},
  },
  inputs: {provider_verified: {label: 'Nguồn cổng đã xác thực', values: [false, true], initial: false}},
  transitions: [
    {event: 'confirm', label: 'Xác nhận thu tiền', from_states: ['CREATED'], to_state: 'SUCCEEDED',
     guard: '$input.provider_verified', effects: {}},
    {event: 'ship', label: 'Yêu cầu giao hàng', from_states: ['SUCCEEDED'], to_state: 'SUCCEEDED',
     guard: {not: ['$shipped']}, effects: {shipped: true}},
  ],
  properties: [{id: 'no_unpaid_shipping', label: 'Chỉ giao hàng khi đã thu tiền',
                expression: {implies: ['$shipped', {eq: ['$status', 'SUCCEEDED']}]}}],
};

export const graph: Graph = {
  nodes: [
    {id: 0, state: {status: 'CREATED', shipped: false}, violations: []},
    {id: 1, state: {status: 'SUCCEEDED', shipped: false}, violations: []},
  ],
  edges: [{source: 0, target: 1, event: 'confirm', inputs: {provider_verified: true}}],
  complete: true, limit: 256, spec_hash: 'abcdef1234567890',
};

export const verification: Verification = {
  spec_hash: 'abcdef1234567890', bound: 12, elapsed_ms: 40, solver: 'Z3 4.16.0',
  scope: 'Safety BMC', results: [{id: 'no_unpaid_shipping', label: 'Chỉ giao hàng khi đã thu tiền',
                                  verdict: 'BOUNDED_SAFE', checked_depth: 12}],
};

export const tests: TestResult = {
  spec_hash: 'abcdef1234567890', elapsed_ms: 12, scope: 'Phân tích tĩnh + kịch bản',
  results: [
    {name: 'Mã sinh không dùng eval, exec hay I/O ngoài', group: 'static', verdict: 'PASS'},
    {name: 'Không hoàn tiền quá số đã thu', group: 'dynamic', verdict: 'SKIP',
     reason: 'Đặc tả không có sự kiện đóng vai trò: refund'},
  ],
};

export const advisory: Advisory = {
  spec_hash: 'abcdef1234567890', scope: 'Gợi ý triển khai suy ra từ đặc tả',
  severity_counts: {critical: 1, high: 1, medium: 0, low: 0},
  coverage_counts: {MODELED: 1, PARTIAL: 0, MISSING: 1, OUTSIDE_MODEL: 0},
  items: [
    {id: 'webhook_authenticity', title: 'Xác thực nguồn webhook trước khi ghi nhận thu tiền',
     severity: 'critical', status: 'MODELED', area: 'Cổng thanh toán',
     evidence: 'Guard của confirm đọc input xác thực nguồn.',
     guidance: ['Kiểm HMAC trên raw body trước khi parse JSON.']},
    {id: 'refund_coverage', title: 'Hoàn tiền chưa được mô hình hóa', severity: 'high',
     status: 'MISSING', area: 'Nghiệp vụ', evidence: 'Không có sự kiện hoàn tiền nào.',
     guidance: ['Thêm biến đếm số tiền đã hoàn với bất biến refunded ≤ captured.']},
  ],
};

/** Route the App's fetch calls to fixtures; extra routes override or add endpoints. */
export function stubApi(routes: Record<string, unknown> = {}) {
  const table: Record<string, unknown> = {
    '/api/spec': {spec, spec_hash: graph.spec_hash},
    '/api/graph': graph,
    '/api/verify': verification,
    '/api/tests': tests,
    '/api/advisory': advisory,
    ...routes,
  };
  const calls: {url: string; body: unknown}[] = [];
  const stub = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({url, body: init?.body ? JSON.parse(String(init.body)) : undefined});
    const payload = table[url];
    if (payload === undefined) return {ok: false, json: async () => ({detail: `Không có route ${url}`})};
    return {ok: true, json: async () => payload};
  });
  vi.stubGlobal('fetch', stub);
  return {calls, stub, table};
}
