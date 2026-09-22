import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ExpressionEditor, nodeFor, tokenOf } from './ExpressionEditor';
import { expression } from './components';
import { spec } from './testFixtures';
import type { Expr } from './types';

function Harness({initial, allowInputs = true}: {initial: Expr; allowInputs?: boolean}) {
  const [expr, setExpr] = useState<Expr>(initial);
  return <>
    <ExpressionEditor expr={expr} spec={spec} allowInputs={allowInputs} onChange={setExpr}/>
    <output data-testid="json">{JSON.stringify(expr)}</output>
  </>;
}
const json = () => screen.getByTestId('json').textContent;

describe('tokenOf', () => {
  it.each([
    [true, 'const:bool'],
    [3, 'const:int'],
    ['SUCCEEDED', 'const:str'],
    ['$shipped', 'ref:shipped'],
    ['$input.provider_verified', 'ref:input.provider_verified'],
    [{and: [true, true]}, 'op:and'],
  ] as [Expr, string][])('describes %j as %s', (expr, token) => {
    expect(tokenOf(expr)).toBe(token);
  });
});

describe('nodeFor', () => {
  it('builds operands matching the operator type', () => {
    expect(nodeFor('op:add', 'X')).toEqual({add: [0, 0]});
    expect(nodeFor('op:and', 'X')).toEqual({and: [true, true]});
    expect(nodeFor('op:not', 'X')).toEqual({not: [true]});
    expect(nodeFor('op:le', 'X')).toEqual({le: [0, 0]});
    expect(nodeFor('op:implies', 'X')).toEqual({implies: [true, true]});
  });

  it('builds variable reads and literals', () => {
    expect(nodeFor('ref:shipped', 'X')).toBe('$shipped');
    expect(nodeFor('ref:input.provider_verified', 'X')).toBe('$input.provider_verified');
    expect(nodeFor('const:int', 'X')).toBe(0);
    expect(nodeFor('const:str', 'CREATED')).toBe('CREATED');
  });
});

it('offers state variables, event inputs and operators', () => {
  render(<Harness initial={true}/>);
  const picker = screen.getByLabelText('Thành phần biểu thức');
  expect(picker).toHaveValue('const:bool');
  const values = [...picker.querySelectorAll('option')].map(option => option.value);
  expect(values).toContain('ref:shipped');
  expect(values).toContain('ref:input.provider_verified');
  expect(values).toContain('op:implies');
});

it('hides event inputs when the expression is an invariant', () => {
  render(<Harness initial={true} allowInputs={false}/>);
  const values = [...screen.getByLabelText('Thành phần biểu thức').querySelectorAll('option')]
    .map(option => option.value);
  expect(values).toContain('ref:shipped');
  expect(values).not.toContain('ref:input.provider_verified');
});

it('replaces the node when a different operator is picked', async () => {
  const user = userEvent.setup();
  render(<Harness initial={true}/>);
  await user.selectOptions(screen.getByLabelText('Thành phần biểu thức'), 'op:implies');
  expect(json()).toBe('{"implies":[true,true]}');
  expect(screen.getAllByLabelText('Thành phần biểu thức')).toHaveLength(3);
});

it('edits a nested branch without touching its sibling', async () => {
  const user = userEvent.setup();
  render(<Harness initial={{implies: ['$shipped', true]}}/>);
  const pickers = screen.getAllByLabelText('Thành phần biểu thức');
  await user.selectOptions(pickers[2], 'ref:status');
  expect(json()).toBe('{"implies":["$shipped","$status"]}');
});

it('adds and removes branches of a variadic operator', async () => {
  const user = userEvent.setup();
  render(<Harness initial={{and: [true, true]}}/>);
  await user.click(screen.getByRole('button', {name: /Thêm nhánh/}));
  expect(json()).toBe('{"and":[true,true,true]}');
  await user.click(screen.getByRole('button', {name: 'Xóa nhánh 2'}));
  expect(json()).toBe('{"and":[true,true]}');
});

it('does not offer removal while a variadic operator has only two branches', () => {
  render(<Harness initial={{and: [true, true]}}/>);
  expect(screen.queryByRole('button', {name: /Xóa nhánh/})).toBeNull();
});

it('offers the sibling domain when comparing against a variable', async () => {
  const user = userEvent.setup();
  render(<Harness initial={{eq: ['$status', 'CREATED']}}/>);
  const literal = screen.getByLabelText('Giá trị hằng');
  expect([...literal.querySelectorAll('option')].map(o => o.textContent)).toEqual(['CREATED', 'SUCCEEDED']);
  await user.selectOptions(literal, JSON.stringify('SUCCEEDED'));
  expect(json()).toBe('{"eq":["$status","SUCCEEDED"]}');
});

it('renders a numeric literal as a number field when no domain applies', async () => {
  const user = userEvent.setup();
  render(<Harness initial={{le: [0, 0]}}/>);
  const fields = screen.getAllByLabelText('Giá trị hằng');
  expect(fields[0]).toHaveAttribute('type', 'number');
  await user.clear(fields[1]);
  await user.type(fields[1], '2');
  expect(json()).toBe('{"le":[0,2]}');
});

it('keeps the rendered formula in step with the edited tree', async () => {
  const user = userEvent.setup();
  render(<Harness initial={true}/>);
  await user.selectOptions(screen.getByLabelText('Thành phần biểu thức'), 'op:not');
  const nested = screen.getAllByLabelText('Thành phần biểu thức')[1];
  await user.selectOptions(nested, 'ref:shipped');
  expect(expression(JSON.parse(json()!))).toBe('¬$shipped');
});

it('disables every control while a request is in flight', () => {
  render(<ExpressionEditor expr={{and: [true, true, true]}} spec={spec} allowInputs disabled
    onChange={vi.fn()}/>);
  for (const picker of screen.getAllByLabelText('Thành phần biểu thức')) expect(picker).toBeDisabled();
  expect(screen.getByRole('button', {name: /Thêm nhánh/})).toBeDisabled();
});
