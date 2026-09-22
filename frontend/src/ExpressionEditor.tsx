import { Plus, X } from 'lucide-react';
import type { Expr, Spec, Value, Variable } from './types';

type Arity = 1 | 2 | 'many';
export const OPERATORS: {op: string; label: string; arity: Arity}[] = [
  {op: 'eq', label: '= bằng', arity: 2},
  {op: 'ne', label: '≠ khác', arity: 2},
  {op: 'lt', label: '< nhỏ hơn', arity: 2},
  {op: 'le', label: '≤ nhỏ hơn hoặc bằng', arity: 2},
  {op: 'and', label: '∧ và', arity: 'many'},
  {op: 'or', label: '∨ hoặc', arity: 'many'},
  {op: 'not', label: '¬ phủ định', arity: 1},
  {op: 'implies', label: '⇒ kéo theo', arity: 2},
  {op: 'add', label: '+ cộng', arity: 2},
  {op: 'sub', label: '− trừ', arity: 2},
];
const arityOf = (op: string) => OPERATORS.find(item => item.op === op)?.arity;

/** The select token that describes a node: a literal kind, a variable read, or an operator. */
export function tokenOf(expr: Expr): string {
  if (typeof expr === 'string' && expr.startsWith('$')) return `ref:${expr.slice(1)}`;
  if (typeof expr === 'object') return `op:${Object.keys(expr)[0]}`;
  return `const:${typeof expr === 'boolean' ? 'bool' : typeof expr === 'number' ? 'int' : 'str'}`;
}

/** Build a well-formed default node when the user picks a different token. */
export function nodeFor(token: string, sample: string): Expr {
  const [kind, rest] = [token.slice(0, token.indexOf(':')), token.slice(token.indexOf(':') + 1)];
  if (kind === 'ref') return `$${rest}`;
  if (kind === 'const') return rest === 'bool' ? true : rest === 'int' ? 0 : sample;
  const arity = arityOf(rest);
  const numeric = ['lt', 'le', 'add', 'sub'].includes(rest);
  const operand: Expr = numeric ? 0 : true;
  if (arity === 1) return {[rest]: [operand]};
  if (arity === 'many') return {[rest]: [true, true]};
  return {[rest]: [operand, operand]};
}

function stringSample(spec: Spec): string {
  for (const variable of Object.values(spec.variables)) {
    if (typeof variable.values[0] === 'string') return String(variable.values[0]);
  }
  return 'value';
}

/** Domain values offered for a literal, when the sibling of a comparison names a variable. */
function siblingDomain(spec: Spec, parent?: Expr, index?: number): Variable | undefined {
  if (typeof parent !== 'object' || index === undefined) return undefined;
  const args = Object.values(parent)[0];
  const sibling = args[index === 0 ? 1 : 0];
  if (typeof sibling !== 'string' || !sibling.startsWith('$')) return undefined;
  const name = sibling.slice(1);
  return name.startsWith('input.') ? spec.inputs[name.slice(6)] : spec.variables[name];
}

function Literal({value, domain, disabled, onChange}: {
  value: Value; domain?: Variable; disabled?: boolean; onChange: (next: Value) => void;
}) {
  if (domain && domain.values.some(item => typeof item === typeof value)) {
    return <select aria-label="Giá trị hằng" value={JSON.stringify(value)} disabled={disabled}
      onChange={event => onChange(JSON.parse(event.target.value))}>
      {domain.values.map(item => <option key={String(item)} value={JSON.stringify(item)}>{String(item)}</option>)}
    </select>;
  }
  if (typeof value === 'boolean') {
    return <select aria-label="Giá trị hằng" value={String(value)} disabled={disabled}
      onChange={event => onChange(event.target.value === 'true')}>
      <option value="true">true</option><option value="false">false</option>
    </select>;
  }
  if (typeof value === 'number') {
    return <input aria-label="Giá trị hằng" type="number" value={value} disabled={disabled}
      onChange={event => onChange(Number(event.target.value))}/>;
  }
  return <input aria-label="Giá trị hằng" value={value} disabled={disabled}
    onChange={event => onChange(event.target.value)}/>;
}

export function ExpressionEditor({expr, spec, allowInputs, disabled, onChange, parent, index, depth = 0}: {
  expr: Expr;
  spec: Spec;
  allowInputs: boolean;
  disabled?: boolean;
  onChange: (next: Expr) => void;
  parent?: Expr;
  index?: number;
  depth?: number;
}) {
  const token = tokenOf(expr);
  const isOperator = typeof expr === 'object';
  const op = isOperator ? Object.keys(expr)[0] : '';
  const args = isOperator ? Object.values(expr)[0] : [];
  const arity = arityOf(op);

  function replaceArg(position: number, next: Expr) {
    onChange({[op]: args.map((item, i) => (i === position ? next : item))});
  }

  return <div className={`expr-node${depth ? '' : ' root'}`}>
    <div className="expr-row">
      <select aria-label="Thành phần biểu thức" className="expr-token" value={token} disabled={disabled}
        onChange={event => onChange(nodeFor(event.target.value, stringSample(spec)))}>
        <optgroup label="Hằng">
          <option value="const:bool">Hằng true / false</option>
          <option value="const:int">Hằng số nguyên</option>
          <option value="const:str">Hằng chuỗi</option>
        </optgroup>
        <optgroup label="Biến trạng thái">
          {Object.entries(spec.variables).map(([name, variable]) =>
            <option key={name} value={`ref:${name}`}>${name} — {variable.label}</option>)}
        </optgroup>
        {allowInputs && <optgroup label="Tham số sự kiện">
          {Object.entries(spec.inputs).map(([name, variable]) =>
            <option key={name} value={`ref:input.${name}`}>$input.{name} — {variable.label}</option>)}
        </optgroup>}
        <optgroup label="Toán tử">
          {OPERATORS.map(item => <option key={item.op} value={`op:${item.op}`}>{item.label}</option>)}
        </optgroup>
      </select>
      {!isOperator && token.startsWith('const:') &&
        <Literal value={expr as Value} domain={siblingDomain(spec, parent, index)} disabled={disabled}
          onChange={next => onChange(next)}/>}
      {isOperator && arity === 'many' && <button type="button" className="expr-add" disabled={disabled}
        onClick={() => onChange({[op]: [...args, true]})}><Plus size={13}/> Thêm nhánh</button>}
    </div>
    {isOperator && <div className="expr-children">
      {args.map((arg, position) => <div className="expr-branch" key={position}>
        <ExpressionEditor expr={arg} spec={spec} allowInputs={allowInputs} disabled={disabled}
          parent={expr} index={position} depth={depth + 1}
          onChange={next => replaceArg(position, next)}/>
        {arity === 'many' && args.length > 2 && <button type="button" className="icon-button expr-remove"
          aria-label={`Xóa nhánh ${position + 1}`} disabled={disabled}
          onClick={() => onChange({[op]: args.filter((_, i) => i !== position)})}><X size={14}/></button>}
      </div>)}
    </div>}
  </div>;
}
