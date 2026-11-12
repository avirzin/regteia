// Minimal SVG charts following the dataviz mark specs: bars <= 24px, 4px rounded data-end (square at the
// baseline), 2px surface gap between touching fills, hairline grid, text in ink tokens, per-mark tooltip on
// hover and focus, and a table view for every chart. Labels are inserted with textContent only.
import { fmt, fmtCompacto, localeIntl, t } from './i18n'

const NS = 'http://www.w3.org/2000/svg'
const BAR = 18 // bar thickness (<= 24)
const RAIO = 4
const GAP = 2

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  text?: string,
): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v)
  if (text !== undefined) e.textContent = text
  return e
}

function s<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}): SVGElementTagNameMap[K] {
  const e = document.createElementNS(NS, tag)
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v))
  return e
}

// ---- tooltip (one per page) ----
let dica: HTMLDivElement | null = null
export function mostrarDica(x: number, y: number, valor: string, rotulo: string, extra?: string): void {
  if (!dica) {
    dica = el('div', { class: 'dica', role: 'tooltip' })
    document.body.append(dica)
  }
  dica.replaceChildren(el('strong', {}, valor), el('div', { class: 'sec' }, rotulo))
  if (extra) dica.append(el('div', { class: 'sec' }, extra))
  dica.style.display = 'block'
  const r = dica.getBoundingClientRect()
  dica.style.left = `${Math.min(x + 14, window.innerWidth - r.width - 8)}px`
  dica.style.top = `${Math.min(y + 14, window.innerHeight - r.height - 8)}px`
}
export function esconderDica(): void {
  if (dica) dica.style.display = 'none'
}

function ligarDica(g: SVGGElement, valor: string, rotulo: string, extra?: string): void {
  g.setAttribute('tabindex', '0')
  g.setAttribute('role', 'img')
  g.setAttribute('aria-label', `${rotulo}: ${valor}${extra ? `, ${extra}` : ''}`)
  g.addEventListener('pointermove', (e) => mostrarDica(e.clientX, e.clientY, valor, rotulo, extra))
  g.addEventListener('pointerleave', esconderDica)
  g.addEventListener('focus', () => {
    const r = g.getBoundingClientRect()
    mostrarDica(r.right, r.top, valor, rotulo, extra)
  })
  g.addEventListener('blur', esconderDica)
}

// Horizontal bar from x0 to x1, rounded only at the data end (right) when `fim`.
function barraH(x0: number, x1: number, y: number, h: number, fim: boolean): string {
  const w = Math.max(0, x1 - x0)
  const r = fim ? Math.min(RAIO, w, h / 2) : 0
  return `M${x0},${y}H${x0 + w - r}${r ? `A${r},${r} 0 0 1 ${x0 + w},${y + r}` : ''}V${y + h - r}${
    r ? `A${r},${r} 0 0 1 ${x0 + w - r},${y + h}` : ''
  }H${x0}Z`
}

// Vertical column from baseline yb up to yt, rounded at the top.
function colunaV(x: number, w: number, yt: number, yb: number): string {
  const h = Math.max(0, yb - yt)
  const r = Math.min(RAIO, h, w / 2)
  return `M${x},${yb}V${yt + r}A${r},${r} 0 0 1 ${x + r},${yt}H${x + w - r}A${r},${r} 0 0 1 ${x + w},${yt + r}V${yb}Z`
}

function ticks(max: number, comprimento = 320): number[] {
  const n = Math.max(2, Math.min(5, Math.floor(comprimento / 80)))
  if (max <= 0) return [0]
  const passo0 = max / n
  const mag = 10 ** Math.floor(Math.log10(passo0))
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= passo0) ?? passo0
  const out: number[] = []
  for (let v = 0; v <= max + 1e-9; v += passo) out.push(v)
  if (out[out.length - 1] < max) out.push(out[out.length - 1] + passo)
  return out
}

function fmtTick(v: number, max: number): string {
  return max >= 10_000 ? fmtCompacto.format(v) : fmt.format(v)
}

function tabela(cabecalho: string[], linhas: (string | number)[][]): HTMLDetailsElement {
  const d = el('details', { class: 'tabela' })
  d.append(el('summary', {}, t('graficos.verTabela')))
  const tb = el('table')
  const trh = el('tr')
  cabecalho.forEach((c, i) => trh.append(el('th', i > 0 ? { class: 'num' } : {}, c)))
  tb.append(el('thead'), el('tbody'))
  tb.tHead!.append(trh)
  for (const l of linhas) {
    const tr = el('tr')
    l.forEach((c, i) => tr.append(el('td', typeof c === 'number' ? { class: 'num' } : i > 0 ? { class: 'num' } : {}, typeof c === 'number' ? fmt.format(c) : c)))
    tb.tBodies[0].append(tr)
  }
  d.append(tb)
  return d
}

export interface Linha {
  rotulo: string
  valor: number
  extra?: string
}

/** Ranked horizontal bars, one series (one hue). Value printed at the bar tip. */
export function barras(alvo: HTMLElement, linhas: Linha[], opts: { cor?: string; rotuloLargura?: number; tabelaLinhas?: Linha[]; cabecalho?: [string, string] } = {}): void {
  const largura = Math.max(320, alvo.clientWidth)
  const rl = opts.rotuloLargura ?? 190
  const passo = BAR + 10
  const altura = linhas.length * passo + 24
  const max = Math.max(...linhas.map((l) => l.valor), 1)
  const plotW = largura - rl - 64
  const tk = ticks(max, plotW)
  const xmax = tk[tk.length - 1]
  const x = (v: number) => rl + (v / xmax) * plotW
  const svg = s('svg', { class: 'grafico', viewBox: `0 0 ${largura} ${altura}`, height: altura })
  const grade = s('g', { class: 'grade' })
  const eixo = s('g', { class: 'eixo' })
  for (const t of tk) {
    grade.append(s('line', { x1: x(t), x2: x(t), y1: 0, y2: linhas.length * passo }))
    const tx = s('text', { x: x(t), y: altura - 6, 'text-anchor': 'middle' })
    tx.textContent = fmtTick(t, xmax)
    eixo.append(tx)
  }
  svg.append(grade, eixo)
  linhas.forEach((l, i) => {
    const y = i * passo + 5
    const g = s('g', { class: 'marca' })
    g.append(s('rect', { class: 'alvo', x: 0, y: y - 5, width: largura, height: passo }))
    const rot = s('text', { x: rl - 8, y: y + BAR / 2 + 4, 'text-anchor': 'end' })
    rot.textContent = l.rotulo.length > 30 ? `${l.rotulo.slice(0, 29)}…` : l.rotulo
    g.append(rot, s('path', { d: barraH(x(0), x(l.valor), y, BAR, true), fill: opts.cor ?? 'var(--serie-1)' }))
    const v = s('text', { class: 'valor-barra', x: x(l.valor) + 6, y: y + BAR / 2 + 4 })
    v.textContent = fmt.format(l.valor)
    g.append(v)
    ligarDica(g, fmt.format(l.valor), l.rotulo, l.extra)
    svg.append(g)
  })
  svg.append(s('line', { class: 'base', x1: x(0), x2: x(0), y1: 0, y2: linhas.length * passo }))
  const cab = opts.cabecalho ?? ['', t('graficos.normas')]
  alvo.replaceChildren(svg, tabela(cab, (opts.tabelaLinhas ?? linhas).map((l) => [l.rotulo, l.valor])))
}

export interface Parte {
  chave: string
  rotulo: string
  cor: string
}

/** Stacked horizontal bars (several wholes on one shared axis). 2px surface gap between segments. */
export function empilhadas(alvo: HTMLElement, linhas: { rotulo: string; partes: Record<string, number> }[], partes: Parte[]): void {
  const largura = Math.max(320, alvo.clientWidth)
  const rl = 230
  const passo = BAR + 14
  const altura = linhas.length * passo + 24
  const totais = linhas.map((l) => partes.reduce((a, p) => a + (l.partes[p.chave] ?? 0), 0))
  const plotW = largura - rl - 64
  const tk = ticks(Math.max(...totais, 1), plotW)
  const xmax = tk[tk.length - 1]
  const x = (v: number) => rl + (v / xmax) * plotW

  const legenda = el('div', { class: 'legenda' })
  for (const p of partes) {
    const it = el('span', { class: 'item' })
    const am = el('span', { class: 'amostra' })
    am.style.background = p.cor
    it.append(am, document.createTextNode(p.rotulo))
    legenda.append(it)
  }
  const svg = s('svg', { class: 'grafico', viewBox: `0 0 ${largura} ${altura}`, height: altura })
  const grade = s('g', { class: 'grade' })
  const eixo = s('g', { class: 'eixo' })
  for (const t of tk) {
    grade.append(s('line', { x1: x(t), x2: x(t), y1: 0, y2: linhas.length * passo }))
    const tx = s('text', { x: x(t), y: altura - 6, 'text-anchor': 'middle' })
    tx.textContent = fmtTick(t, xmax)
    eixo.append(tx)
  }
  svg.append(grade, eixo)
  linhas.forEach((l, i) => {
    const y = i * passo + 6
    const rot = s('text', { x: rl - 8, y: y + BAR / 2 + 4, 'text-anchor': 'end' })
    rot.textContent = l.rotulo
    svg.append(rot)
    const presentes = partes.filter((p) => (l.partes[p.chave] ?? 0) > 0)
    let acc = 0
    presentes.forEach((p, j) => {
      const v = l.partes[p.chave]
      const x0 = x(acc) + (j > 0 ? GAP / 2 : 0)
      const x1 = x(acc + v) - (j < presentes.length - 1 ? GAP / 2 : 0)
      acc += v
      const g = s('g', { class: 'marca' })
      g.append(s('rect', { class: 'alvo', x: x0, y: y - 6, width: Math.max(x1 - x0, 4), height: passo }))
      g.append(s('path', { d: barraH(x0, Math.max(x1, x0 + 0.5), y, BAR, j === presentes.length - 1), fill: p.cor }))
      const pct = ((v / totais[i]) * 100).toLocaleString(localeIntl(), { maximumFractionDigits: 1 })
      ligarDica(g, fmt.format(v), `${l.rotulo} · ${p.rotulo}`, t('graficos.pctTotal', { pct }))
      svg.append(g)
    })
    const tot = s('text', { class: 'valor-barra', x: x(totais[i]) + 6, y: y + BAR / 2 + 4 })
    tot.textContent = fmt.format(totais[i])
    svg.append(tot)
  })
  svg.append(s('line', { class: 'base', x1: x(0), x2: x(0), y1: 0, y2: linhas.length * passo }))
  alvo.replaceChildren(
    legenda,
    svg,
    tabela(
      ['', ...partes.map((p) => p.rotulo), t('graficos.total')],
      linhas.map((l, i) => [l.rotulo, ...partes.map((p) => l.partes[p.chave] ?? 0), totais[i]]),
    ),
  )
}

/** Columns over an ordered axis (e.g. decades), one series. Labels only on the extreme. */
export function colunas(alvo: HTMLElement, linhas: Linha[], opts: { cabecalho?: [string, string] } = {}): void {
  const largura = Math.max(320, alvo.clientWidth)
  const altura = 220
  const esq = 48
  const base = altura - 26
  const max = Math.max(...linhas.map((l) => l.valor), 1)
  const tk = ticks(max, base)
  const ymax = tk[tk.length - 1]
  const y = (v: number) => base - (v / ymax) * (base - 12)
  const banda = (largura - esq - 8) / linhas.length
  const w = Math.min(24, banda - GAP * 2)
  const svg = s('svg', { class: 'grafico', viewBox: `0 0 ${largura} ${altura}`, height: altura })
  const grade = s('g', { class: 'grade' })
  const eixo = s('g', { class: 'eixo' })
  for (const t of tk) {
    grade.append(s('line', { x1: esq, x2: largura - 8, y1: y(t), y2: y(t) }))
    const tx = s('text', { x: esq - 6, y: y(t) + 4, 'text-anchor': 'end' })
    tx.textContent = fmtTick(t, ymax)
    eixo.append(tx)
  }
  svg.append(grade, eixo)
  const imax = linhas.reduce((b, l, i) => (l.valor > linhas[b].valor ? i : b), 0)
  linhas.forEach((l, i) => {
    const cx = esq + i * banda + banda / 2
    const g = s('g', { class: 'marca' })
    g.append(s('rect', { class: 'alvo', x: cx - banda / 2, y: 0, width: banda, height: base }))
    g.append(s('path', { d: colunaV(cx - w / 2, w, y(l.valor), base), fill: 'var(--serie-1)' }))
    const tx = s('text', { x: cx, y: altura - 8, 'text-anchor': 'middle', class: 'eixo' })
    tx.textContent = l.rotulo
    g.append(tx)
    if (i === imax) {
      const v = s('text', { class: 'valor-barra', x: cx, y: y(l.valor) - 6, 'text-anchor': 'middle' })
      v.textContent = fmt.format(l.valor)
      g.append(v)
    }
    ligarDica(g, fmt.format(l.valor), l.rotulo, l.extra)
    svg.append(g)
  })
  svg.append(s('line', { class: 'base', x1: esq, x2: largura - 8, y1: base, y2: base }))
  alvo.replaceChildren(svg, tabela(opts.cabecalho ?? ['', t('graficos.normas')], linhas.map((l) => [l.rotulo, l.valor])))
}

export function tabelaSimples(cabecalho: string[], linhas: (string | number | Node)[][]): HTMLTableElement {
  const t = el('table')
  const trh = el('tr')
  cabecalho.forEach((c) => trh.append(el('th', {}, c)))
  t.append(el('thead'), el('tbody'))
  t.tHead!.append(trh)
  for (const l of linhas) {
    const tr = el('tr')
    for (const c of l) {
      const td = el('td', typeof c === 'number' ? { class: 'num' } : {})
      if (c instanceof Node) td.append(c)
      else td.textContent = typeof c === 'number' ? fmt.format(c) : c
      tr.append(td)
    }
    t.tBodies[0].append(tr)
  }
  return t
}
