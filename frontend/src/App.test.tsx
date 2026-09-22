import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { advisory, graph, spec, stubApi } from './testFixtures';

let api: ReturnType<typeof stubApi>;

beforeEach(() => {
  localStorage.clear();
  api = stubApi();
});
afterEach(() => vi.unstubAllGlobals());

async function open(page: string) {
  const user = userEvent.setup();
  render(<App/>);
  await screen.findByText(spec.name);
  await user.click(screen.getByRole('button', {name: new RegExp(page)}));
  return user;
}
const sent = (path: string) => api.calls.filter(call => call.url === `/api${path}`);

it('loads the project and walks the eight workflow steps in order', async () => {
  render(<App/>);
  await screen.findByText(spec.name);
  const steps = within(screen.getByRole('navigation', {name: 'Quy trình phát triển'}))
    .getAllByRole('button').map(button => button.textContent);
  expect(steps).toEqual([
    'Đặc tả chức năng01', 'Ràng buộc02', 'Mô hình Kripke03', 'Kiểm chứng Z304',
    'Sinh mã Python05', 'Phòng mô phỏng06', 'Kiểm thử07', 'Gợi ý triển khai08',
  ]);
  expect(sent('/spec')).toHaveLength(1);
  expect(sent('/graph')).toHaveLength(1);
});

it('shows guards and invariants as editable trees on the constraints page', async () => {
  await open('Ràng buộc');
  expect(screen.getByRole('heading', {name: 'Guard và bất biến'})).toBeInTheDocument();
  expect(screen.getByDisplayValue('Chỉ giao hàng khi đã thu tiền')).toBeInTheDocument();
  expect(screen.getByDisplayValue('no_unpaid_shipping')).toBeInTheDocument();
  // One editor per invariant plus one per transition guard.
  expect(screen.getAllByText(/AG /)).toHaveLength(spec.properties.length);
  expect(screen.getByText('Xác nhận thu tiền')).toBeInTheDocument();
  expect(screen.getByText('Yêu cầu giao hàng')).toBeInTheDocument();
});

it('keeps constraint edits local until they are applied', async () => {
  const user = await open('Ràng buộc');
  const apply = screen.getByRole('button', {name: /Kiểm tra và áp dụng/});
  expect(apply).toBeDisabled();
  await user.clear(screen.getByDisplayValue('Chỉ giao hàng khi đã thu tiền'));
  await user.type(screen.getByRole('textbox', {name: 'Mô tả bằng lời'}), 'Bất biến đã sửa');
  expect(screen.getByText('Có thay đổi chưa áp dụng')).toBeInTheDocument();
  expect(sent('/graph')).toHaveLength(1);

  await user.click(apply);
  await waitFor(() => expect(sent('/graph')).toHaveLength(2));
  expect(sent('/graph')[1].body).toMatchObject({spec: {properties: [{label: 'Bất biến đã sửa'}]}});
  await screen.findByText(/Đã áp dụng ràng buộc mới/);
});

it('restores the applied constraints when the edit is undone', async () => {
  const user = await open('Ràng buộc');
  await user.clear(screen.getByRole('textbox', {name: 'Mô tả bằng lời'}));
  await user.type(screen.getByRole('textbox', {name: 'Mô tả bằng lời'}), 'Tạm thời');
  await user.click(screen.getByRole('button', {name: /Hoàn tác/}));
  expect(screen.getByDisplayValue('Chỉ giao hàng khi đã thu tiền')).toBeInTheDocument();
  expect(screen.getByText('Khớp với mô hình hiện tại')).toBeInTheDocument();
  expect(sent('/graph')).toHaveLength(1);
});

it('adds an invariant with a unique identifier and removes it again', async () => {
  const user = await open('Ràng buộc');
  await user.click(screen.getByRole('button', {name: /Thêm bất biến/}));
  expect(screen.getByDisplayValue('invariant_2')).toBeInTheDocument();
  expect(screen.getAllByText(/AG /)).toHaveLength(2);
  await user.click(screen.getAllByRole('button', {name: /Xóa/})[1]);
  expect(screen.queryByDisplayValue('invariant_2')).toBeNull();
});

it('will not delete the last remaining invariant', async () => {
  await open('Ràng buộc');
  expect(screen.getByRole('button', {name: /Xóa/})).toBeDisabled();
});

it('surfaces a server rejection instead of applying an invalid constraint', async () => {
  const user = await open('Ràng buộc');
  api.table['/api/graph'] = undefined;
  await user.click(screen.getByRole('button', {name: /Thêm bất biến/}));
  await user.click(screen.getByRole('button', {name: /Kiểm tra và áp dụng/}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Không có route /api/graph');
  // The draft is kept so the edit is not lost.
  expect(screen.getByDisplayValue('invariant_2')).toBeInTheDocument();
});

it('reports which upstream results feed the advisory', async () => {
  await open('Gợi ý triển khai');
  expect(screen.getByText('Chưa chạy kiểm chứng Z3')).toBeInTheDocument();
  expect(screen.getByText('Chưa chạy kiểm thử')).toBeInTheDocument();
  expect(screen.getByText('Chưa lập gợi ý cho phiên bản này')).toBeInTheDocument();
});

it('renders the advisory grouped by severity and coverage', async () => {
  const user = await open('Gợi ý triển khai');
  await user.click(screen.getAllByRole('button', {name: /Lập gợi ý/})[0]);
  await screen.findByText(advisory.items[0].title);
  expect(sent('/advisory')[0].body).toMatchObject({verification: null, tests: null});
  // Once in the coverage summary, once as the badge on the single matching card.
  expect(screen.getAllByText('Mô hình đã ràng buộc')).toHaveLength(2);
  expect(screen.getAllByText('Mô hình còn thiếu')).toHaveLength(2);
  expect(screen.getAllByText('Nghiêm trọng')).toHaveLength(2);
  expect(screen.getByText(advisory.items[1].guidance[0])).toBeInTheDocument();
  expect(screen.getByText(/Gợi ý triển khai suy ra từ đặc tả/)).toBeInTheDocument();
});

it('passes the checker and test results into the advisory once they exist', async () => {
  const user = await open('Kiểm chứng Z3');
  await user.click(screen.getByRole('button', {name: /Chạy kiểm chứng/}));
  await screen.findByText('Không tìm thấy lỗi');
  await user.click(screen.getByRole('button', {name: /Kiểm thử07/}));
  await user.click(screen.getByRole('button', {name: /Chạy kiểm thử/}));
  await screen.findByText('Mã sinh không dùng eval, exec hay I/O ngoài');

  await user.click(screen.getByRole('button', {name: /Gợi ý triển khai08/}));
  expect(screen.getByText(`Đã có kết quả Z3 #${graph.spec_hash.slice(0, 8)}`)).toBeInTheDocument();
  await user.click(screen.getAllByRole('button', {name: /Lập gợi ý/})[0]);
  await screen.findByText(advisory.items[0].title);
  const body = sent('/advisory')[0].body as {verification: unknown; tests: unknown};
  expect(body.verification).toBeTruthy();
  expect(body.tests).toBeTruthy();
});

it('shows static and dynamic groups in the test report', async () => {
  const user = await open('Kiểm thử07');
  await user.click(screen.getByRole('button', {name: /Chạy kiểm thử/}));
  await screen.findByText('Mã sinh không dùng eval, exec hay I/O ngoài');
  expect(screen.getByText('Tĩnh · cú pháp')).toBeInTheDocument();
  expect(screen.getByText('Động · nghiệp vụ')).toBeInTheDocument();
  // Once as the metric label, once as the verdict badge on the skipped row.
  expect(screen.getAllByText('Bỏ qua')).toHaveLength(2);
  expect(screen.getByText(/không có sự kiện đóng vai trò/i)).toBeInTheDocument();
});

it('loads the refund example from the model page', async () => {
  const refundSpec = {...spec, name: 'Thanh toán — hoàn tiền'};
  api.table['/api/examples/refund'] = {spec: refundSpec};
  const user = await open('Mô hình Kripke');
  await user.click(screen.getByRole('button', {name: 'Mẫu hoàn tiền'}));
  await screen.findByText('Thanh toán — hoàn tiền');
  expect(screen.getByText(/thu một phần, hoàn tiền từng phần/)).toBeInTheDocument();
});

it('discards stale results when a new specification is installed', async () => {
  const user = await open('Kiểm chứng Z3');
  await user.click(screen.getByRole('button', {name: /Chạy kiểm chứng/}));
  await screen.findByText('Không tìm thấy lỗi');
  api.table['/api/examples/refund'] = {spec: {...spec, name: 'Bản khác'}};
  await user.click(screen.getByRole('button', {name: /Mô hình Kripke/}));
  await user.click(screen.getByRole('button', {name: 'Mẫu hoàn tiền'}));
  await screen.findByText('Bản khác');
  await user.click(screen.getByRole('button', {name: /Kiểm chứng Z3/}));
  expect(screen.getByText('Sẵn sàng tìm phản ví dụ')).toBeInTheDocument();
});
