import { useMemo } from 'react';
import { Expand } from 'lucide-react';
import type { Graph, Trace } from './types';
import { Badge } from './components';

export function GraphView({graph, selected, onSelect, trace}: {graph: Graph; selected: number; onSelect: (id: number) => void; trace?: Trace[]}) {
  const {positions, width, height} = useMemo(() => {
    const levels = new Map<number, number>([[0, 0]]);
    const queue = [0];
    for (let i = 0; i < queue.length; i++) {
      for (const edge of graph.edges.filter(e => e.source === queue[i] && e.event !== 'stutter')) {
        if (!levels.has(edge.target)) {levels.set(edge.target, levels.get(queue[i])! + 1); queue.push(edge.target);}
      }
    }
    const columns: Record<number, number[]> = {};
    graph.nodes.slice(0, 64).forEach(n => {(columns[levels.get(n.id) || 0] ||= []).push(n.id);});
    const maxRows = Math.max(...Object.values(columns).map(c => c.length));
    const height = Math.max(430, maxRows * 150 + 90);
    const positions: Record<number, {x: number; y: number}> = {};
    Object.entries(columns).forEach(([level, ids]) => ids.forEach((id, i) => {
      positions[id] = {x: 40 + Number(level) * 245, y: height / 2 + (i - (ids.length - 1) / 2) * 150 - 42};
    }));
    return {positions, width: Math.max(880, Object.keys(columns).length * 245 + 20), height};
  }, [graph]);
  const traceNode = (id: number) => trace?.some(t => Object.entries(graph.nodes[id].state).every(([k,v]) => t.state[k] === v));
  const traceEdge = (source: number, target: number, event: string) => trace?.some((t, i) => i > 0 && t.event === event &&
    Object.entries(graph.nodes[source].state).every(([k,v]) => trace[i-1].state[k] === v) &&
    Object.entries(graph.nodes[target].state).every(([k,v]) => t.state[k] === v));
  const edges = graph.edges.filter(e => e.event !== 'stutter' && positions[e.source] && positions[e.target]);
  return <div className="graph-frame"><div className="graph-caption"><span><span className="dot"/> Trạng thái có thể đạt tới</span><span><Expand size={14}/> Chọn nút để xem biến</span></div>
    <div className="graph-scroll"><svg className="state-graph" viewBox={`0 0 ${width} ${height}`} style={{minWidth: Math.min(width, 1100)}} role="img" aria-label="Đồ thị Kripke của các trạng thái có thể đạt tới">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor"/></marker><marker id="arrow-error" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--destructive)"/></marker></defs>
      {edges.map((edge, i) => {
        const a = positions[edge.source], b = positions[edge.target];
        const backward = b.x <= a.x;
        const x1 = backward ? a.x + 90 : a.x + 180, x2 = backward ? b.x + 90 : b.x;
        const y1 = backward ? a.y : a.y + 42, y2 = backward ? b.y : b.y + 42;
        const path = backward ? `M${x1},${y1} C${x1+65},${y1-95} ${x2-65},${y2-95} ${x2},${y2}` : `M${x1},${y1} C${x1+36},${y1} ${x2-36},${y2} ${x2},${y2}`;
        const active = traceEdge(edge.source, edge.target, edge.event);
        return <g key={`${edge.source}-${edge.target}-${i}`} className={active ? 'edge error' : 'edge'}><path d={path} markerEnd={`url(#${active ? 'arrow-error' : 'arrow'})`}/><text x={(x1+x2)/2} y={backward ? Math.min(y1,y2)-62 : (y1+y2)/2-8} textAnchor="middle">{edge.event}</text></g>;
      })}
      {graph.nodes.slice(0, 64).map(node => {
        const p = positions[node.id];
        return <g key={node.id} transform={`translate(${p.x} ${p.y})`} role="button" tabIndex={0} aria-label={`Trạng thái s${node.id}: ${node.state.status}`} onClick={() => onSelect(node.id)} onKeyDown={e => {if(e.key === 'Enter' || e.key === ' ') {e.preventDefault(); onSelect(node.id);}}} className={`graph-node ${selected === node.id ? 'selected' : ''} ${node.violations.length || traceNode(node.id) ? 'trace' : ''}`}>
          <rect width="180" height="84" rx="9"/><text className="node-id" x="14" y="23">s{node.id}{node.id === 0 ? ' · Khởi đầu' : ''}</text><text className="node-status" x="14" y="47">{String(node.state.status)}</text><text className="node-meta" x="14" y="68">{node.state.shipped ? 'Đã yêu cầu giao hàng' : `Xác nhận thu tiền: ${node.state.captured_count ?? '—'}`}</text><circle cx="160" cy="21" r="4"/>
        </g>;
      })}
    </svg></div><div className="graph-footer"><span>R có self-loop tại mỗi nút (ẩn trên hình).</span><Badge>{graph.nodes.length} nút · {graph.edges.length} cạnh</Badge></div>
    {(!graph.complete || graph.nodes.length > 64) && <p className="notice">Hình chỉ hiển thị tối đa 64 nút; khám phá tối đa {graph.limit} nút. {graph.complete ? 'Đã khám phá đủ.' : 'Đồ thị bị cắt; không xem đây là chứng minh đầy đủ.'}</p>}
  </div>;
}
