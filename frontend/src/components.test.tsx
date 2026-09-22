import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Badge, Code, Empty, Modal, StateValues, expression } from './components';
import type { Expr } from './types';

it.each([
  [true, 'true'],
  ['$shipped', '$shipped'],
  [{not: ['$shipped']}, '¬$shipped'],
  [{eq: ['$status', 'SUCCEEDED']}, '($status = SUCCEEDED)'],
  [{le: ['$captured_count', 1]}, '($captured_count ≤ 1)'],
  [{add: ['$captured_count', 1]}, '($captured_count + 1)'],
  [{and: ['$a', '$b', '$c']}, '($a ∧ $b ∧ $c)'],
  [{implies: ['$shipped', {and: ['$paid', {ne: ['$status', 'FAILED']}]}]},
   '($shipped ⇒ ($paid ∧ ($status ≠ FAILED)))'],
] as [Expr, string][])('renders %j as %s', (expr, text) => {
  expect(expression(expr)).toBe(text);
});

it('renders state values as a definition list', () => {
  render(<StateValues state={{status: 'SUCCEEDED', shipped: true, captured_count: 1}}/>);
  expect(screen.getByText('status').nextSibling).toHaveTextContent('SUCCEEDED');
  expect(screen.getByText('shipped').nextSibling).toHaveTextContent('true');
  expect(screen.getByText('captured_count').nextSibling).toHaveTextContent('1');
});

it('marks a dangerous badge apart from a neutral one', () => {
  render(<><Badge tone="danger">Vi phạm</Badge><Badge>Giá trị biến</Badge></>);
  expect(screen.getByText('Vi phạm')).toHaveClass('badge', 'danger');
  expect(screen.getByText('Giá trị biến')).toHaveClass('badge', 'neutral');
});

it('copies generated source and confirms it', async () => {
  // userEvent.setup() installs its own clipboard, so spy on it afterwards.
  const user = userEvent.setup();
  const writeText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue(undefined);
  render(<Code source="SPEC_HASH = 'abc'"/>);
  await user.click(screen.getByRole('button', {name: 'Sao chép mã'}));
  expect(writeText).toHaveBeenCalledWith("SPEC_HASH = 'abc'");
  expect(await screen.findByText('Đã sao chép')).toBeInTheDocument();
  writeText.mockRestore();
});

it('tells the user to copy by hand when the clipboard is unavailable', async () => {
  const user = userEvent.setup();
  const writeText = vi.spyOn(navigator.clipboard, 'writeText')
    .mockRejectedValue(new Error('denied'));
  render(<Code source="x = 1"/>);
  await user.click(screen.getByRole('button', {name: 'Sao chép mã'}));
  expect(await screen.findByText('Hãy chọn và sao chép thủ công')).toBeInTheDocument();
  writeText.mockRestore();
});

it('closes the editor dialog from the backdrop and the close button', async () => {
  const close = vi.fn();
  const user = userEvent.setup();
  const {container} = render(<Modal title="Chỉnh sửa đặc tả JSON" close={close}><p>Nội dung</p></Modal>);
  await user.click(screen.getByRole('button', {name: 'Đóng trình chỉnh sửa'}));
  expect(close).toHaveBeenCalledTimes(1);
  await user.click(container.querySelector('.modal-backdrop')!);
  expect(close).toHaveBeenCalledTimes(2);
});

it('does not close the dialog when its own content is clicked', async () => {
  const close = vi.fn();
  const user = userEvent.setup();
  render(<Modal title="Chỉnh sửa đặc tả JSON" close={close}><p>Nội dung</p></Modal>);
  await user.click(screen.getByText('Nội dung'));
  expect(close).not.toHaveBeenCalled();
});

it('renders an empty state with its explanation', () => {
  render(<Empty title="Chưa chạy kiểm thử">Các kịch bản kiểm tra giao hàng sớm.</Empty>);
  expect(screen.getByRole('heading', {name: 'Chưa chạy kiểm thử'})).toBeInTheDocument();
  expect(screen.getByText(/giao hàng sớm/)).toBeInTheDocument();
});
