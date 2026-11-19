// Norm page: header (status, official source, notes), "in force on [date]" switch, text by article, amendment
// timeline and the neighborhood graph (Cytoscape + dagre, older norms on the left).
//
// Status on a date comes from GET /api/vigencia/dispositivos (query.vigencia_dispositivos): the page never decides
// it. When the stored text is later wording than the chosen date, it says so and keeps that text folded away: the
// graph doesn't have the wording of that date and the page never presents the current one as it.
import { api, ErroApi, type CitacoesTexto, type DispositivoTexto, type EventoVigencia, type NormaDetalhe, type NormaResumo, type Situacao, type Subgrafo, type TextoNorma, type VigenciaDispositivo, type VigenciaNorma } from './api'
import { el, esconderDica, mostrarDica } from './charts'
import { fmt, fmtData, idioma, t, tDinamico } from './i18n'

const GRUPO_VAR: Record<string, string> = {
  CMN: '--grupo-cmn',
  BCB: '--grupo-bcb',
  CVM: '--grupo-cvm',
  'Lei federal': '--grupo-lei',
  Outros: '--grupo-outros',
}
const TIPOS_RELACAO = ['REVOGA', 'REVOGA_PARCIAL', 'ALTERA', 'CITA', 'REGULAMENTA', 'CONJUNTA']
// line style per relation: identity by dash pattern and weight, not by another hue
const LINHA: Record<string, { estilo: 'solid' | 'dashed' | 'dotted'; largura: number }> = {
  REVOGA: { estilo: 'solid', largura: 2 },
  REVOGA_PARCIAL: { estilo: 'dashed', largura: 2 },
  ALTERA: { estilo: 'solid', largura: 1 },
  CITA: { estilo: 'dotted', largura: 1 },
  REGULAMENTA: { estilo: 'dashed', largura: 1 },
  CONJUNTA: { estilo: 'dotted', largura: 2 },
}

const hojeISO = (): string => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const token = (nome: string) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim()
const situacaoRotulo = (s: Situacao) => tDinamico(`norma.situacao.${s}`, s)
const estadoRotulo = (e: string) => tDinamico(`estado.${e}`, e)
const tipoEvento = (e: EventoVigencia['tipo']) => tDinamico(`norma.evento.${e}`, e)
export const linkNorma = (id: string) => `#/norma/${encodeURIComponent(id)}`

function linkSeguro(href: string | null, texto: string): HTMLElement {
  if (!href || !/^https?:\/\//.test(href)) return el('span', {}, texto)
  return el('a', { href, target: '_blank', rel: 'noopener noreferrer' }, texto)
}

function aviso(api_aviso: string): string {
  // the API's disclaimer is Portuguese; other languages show the same text from the locale file
  return idioma() === 'pt-BR' ? api_aviso : t('app.aviso')
}

// ---------------------------------------------------------------- header

function cabecalho(d: NormaDetalhe): HTMLElement {
  const n = d.norma
  const cab = el('header', { class: 'cab-norma' })
  const estado = n.externo ? 'externa' : (n.estado ?? '')
  cab.append(el('h1', {}, n.titulo ?? n.id))
  const meta = el('p', { class: 'meta' })
  meta.append(el('span', { class: `selo ${estado}` }, estadoRotulo(estado)))
  meta.append(document.createTextNode(`  ${n.id}${n.data ? ` · ${fmtData(n.data)}` : ''}${n.orgao ? ` · ${n.orgao}` : ''}`))
  cab.append(meta)
  const links = el('p', { class: 'links' })
  if (n.fonte_url) links.append(linkSeguro(n.fonte_url, t('visao.fonteOficial')))
  if (n.url_arquivo) links.append(document.createTextNode(' · '), linkSeguro(n.url_arquivo, t('visao.arquivo')))
  if (n.url_externa) links.append(document.createTextNode(' · '), linkSeguro(n.url_externa, t('visao.ondeEsta')))
  if (links.childNodes.length) cab.append(links)
  if (n.ementa) cab.append(el('p', { class: 'ementa' }, n.ementa))
  for (const nota of d.notas) cab.append(el('p', { class: 'nota' }, `⚠ ${nota}`))
  const rel = d.relacoes.filter((g) => g.direcao === 'entrada' && ['REVOGA', 'REVOGA_PARCIAL', 'ALTERA'].includes(g.tipo))
  for (const g of rel) {
    const p = el('p', { class: 'nota' })
    p.append(el('strong', {}, `${tDinamico(`direcao.${g.direcao}.${g.tipo}`, g.tipo)}: `))
    g.itens.forEach((v, i) => {
      if (i) p.append(document.createTextNode(', '))
      p.append(el('a', { href: linkNorma(v.norma.id) }, v.norma.titulo ?? v.norma.id))
      if (v.desde) p.append(document.createTextNode(` (${t('visao.aPartirDe', { data: fmtData(v.desde) })})`))
    })
    if (g.total > g.itens.length) p.append(document.createTextNode(` ${t('visao.eMais', { n: fmt.format(g.total - g.itens.length) })}`))
    cab.append(p)
  }
  for (const c of [...d.citacoes_texto].sort((a, b) => (a.direcao === 'entrada' ? -1 : 1) - (b.direcao === 'entrada' ? -1 : 1))) {
    cab.append(citacoes(c))
  }
  return cab
}

/** Norms cited in this norm's articles (saida), or norms whose articles cite it (entrada), from the text. */
function citacoes(c: CitacoesTexto): HTMLElement {
  const det = el('details', { class: 'citacoes' })
  const titulo = c.direcao === 'entrada' ? t('norma.citadaNoTexto') : t('norma.citaNoTexto')
  det.append(el('summary', {}, `${titulo} (${t('norma.citacoesResumo', { n: fmt.format(c.total) })})`))
  const ul = el('ul')
  for (const x of c.itens) {
    const li = el('li')
    li.append(linkCitada(x.norma))
    const onde = x.dispositivos.map((d) => d.rotulo).join(', ') + (x.total > x.dispositivos.length ? ', …' : '')
    li.append(el('span', { class: 'onde' }, ` · ${t('norma.dispositivosQueCitam', { n: fmt.format(x.total) })}: ${onde}`))
    ul.append(li)
  }
  if (c.total > c.itens.length) ul.append(el('li', { class: 'nota' }, t('visao.eMais', { n: fmt.format(c.total - c.itens.length) })))
  det.append(ul, el('p', { class: 'nota' }, t('norma.citacoesNota')))
  return det
}

function linkCitada(n: NormaResumo): HTMLElement {
  const a = el('a', { href: linkNorma(n.id), class: `citada ${n.externo ? 'externa' : (n.estado ?? '')}`, title: n.id }, n.titulo ?? n.id)
  if (n.estado === 'revogada') a.title = `${n.id} · ${estadoRotulo('revogada')}`
  return a
}

function cita(d: DispositivoTexto): HTMLElement | null {
  if (!d.cita?.length) return null
  const p = el('p', { class: 'cita' })
  p.append(el('span', { class: 'rotulo' }, t('norma.cita')))
  d.cita.forEach((n, i) => {
    p.append(document.createTextNode(i ? ', ' : ' '))
    p.append(linkCitada(n))
  })
  return p
}

// ---------------------------------------------------------------- text by article

function textoBloco(texto: string): HTMLElement {
  return el('div', { class: 'texto-disp' }, texto)
}

function anteriores(d: DispositivoTexto): HTMLElement | null {
  if (!d.redacoes_anteriores.length) return null
  const det = el('details', { class: 'anteriores' })
  det.append(el('summary', {}, t('norma.anteriores', { n: fmt.format(d.redacoes_anteriores.length) })))
  det.append(el('p', { class: 'nota' }, t('norma.anterioresNota')))
  for (const a of d.redacoes_anteriores) det.append(el('div', { class: 'texto-disp riscado' }, a))
  return det
}

function dobrado(rotulo: string, texto: string): HTMLElement {
  const det = el('details', { class: 'dobrado' })
  det.append(el('summary', {}, rotulo), textoBloco(texto))
  return det
}

/** One Dispositivo as it stood on the chosen date. */
function artigo(v: VigenciaDispositivo, d: DispositivoTexto | undefined, data: string): HTMLElement {
  const a = el('article', { class: `disp ${v.situacao} ${v.texto_na_data}`, id: `d-${v.chave}` })
  const h = el('h3')
  h.append(el('a', { href: `#d-${v.chave}`, class: 'ancora' }, v.rotulo))
  const normal = v.situacao === 'vigente' && v.texto_na_data === 'armazenado'
  if (!normal) h.append(el('span', { class: `selo ${v.situacao}` }, situacaoRotulo(v.situacao)))
  if (v.eventos) h.append(el('span', { class: 'contagem' }, t('norma.alteracoes', { n: fmt.format(v.eventos) })))
  a.append(h)
  if (d?.contexto) a.append(el('p', { class: 'contexto' }, d.contexto))
  const dataFmt = fmtData(data)
  if (!v.no_texto) {
    a.append(el('p', { class: 'motivo' }, v.motivo))
    a.append(el('p', { class: 'nota' }, t('norma.semTextoPortal')))
    return a
  }
  if (!d) return a
  if (normal) {
    a.append(textoBloco(d.texto))
  } else if (v.situacao === 'vigente' && v.texto_na_data === 'desconhecido') {
    a.append(el('p', { class: 'motivo alerta' }, t('norma.textoPosterior', { data: dataFmt, n: fmt.format(v.posteriores) })))
    a.append(dobrado(t('norma.verTextoAtual'), d.texto))
  } else {
    a.append(el('p', { class: 'motivo' }, v.motivo))
    a.append(dobrado(t('norma.verTextoArmazenado'), d.texto))
  }
  const c = cita(d)
  if (c) a.append(c)
  const ant = anteriores(d)
  if (ant) a.append(ant)
  return a
}

function sumario(v: VigenciaNorma): HTMLElement {
  const det = el('details', { class: 'sumario' })
  const contagem: Partial<Record<Situacao, number>> = {}
  let posteriores = 0
  for (const d of v.dispositivos) {
    contagem[d.situacao] = (contagem[d.situacao] ?? 0) + 1
    if (d.situacao === 'vigente' && d.texto_na_data === 'desconhecido') posteriores++
  }
  const partes = (Object.entries(contagem) as [Situacao, number][]).map(([s, n]) => `${fmt.format(n)} ${situacaoRotulo(s).toLowerCase()}`)
  if (posteriores) partes.push(t('norma.resumoPosteriores', { n: fmt.format(posteriores) }))
  det.append(el('summary', {}, `${t('norma.sumario', { n: fmt.format(v.dispositivos.length) })} · ${partes.join(' · ')}`))
  const lista = el('ol')
  for (const d of v.dispositivos) {
    const li = el('li', { class: d.situacao })
    li.append(el('a', { href: `#d-${d.chave}` }, d.rotulo))
    if (d.situacao !== 'vigente') li.append(document.createTextNode(` · ${situacaoRotulo(d.situacao).toLowerCase()}`))
    else if (d.texto_na_data === 'desconhecido') li.append(document.createTextNode(' · *'))
    lista.append(li)
  }
  det.append(lista)
  return det
}

// ---------------------------------------------------------------- timeline

interface Grupo {
  data: string | null
  por: EventoVigencia['por']
  eventos: EventoVigencia[]
}

function agrupar(eventos: EventoVigencia[]): Grupo[] {
  const out: Grupo[] = []
  const idx = new Map<string, Grupo>()
  for (const e of eventos) {
    const k = `${e.data ?? ''}|${e.por?.id ?? ''}`
    let g = idx.get(k)
    if (!g) {
      g = { data: e.data, por: e.por, eventos: [] }
      idx.set(k, g)
      out.push(g)
    }
    g.eventos.push(e)
  }
  return out
}

function alvo(e: EventoVigencia): HTMLElement {
  const span = el('span')
  if (e.alcance === 'norma') {
    span.textContent = t('norma.normaInteira')
    return span
  }
  const chave = e.dispositivo?.split('#')[1]
  span.append(chave ? el('a', { href: `#d-${chave}` }, e.rotulo ?? chave) : document.createTextNode(e.rotulo ?? ''))
  if (e.detalhe) span.append(document.createTextNode(`, ${e.detalhe}`))
  if (!e.no_texto) span.append(document.createTextNode(` (${t('norma.foraDoTexto')})`))
  return span
}

function linhaDoTempo(v: VigenciaNorma, onData: (iso: string) => void): HTMLElement {
  const sec = el('section', { class: 'cartao linha-tempo' })
  sec.append(el('h2', {}, t('norma.linhaTempo')))
  sec.append(el('p', { class: 'sub' }, t('norma.linhaTempoSub')))
  const hoje = hojeISO()
  const ol = el('ol', { class: 'eventos' })
  const marcador = (classe: string, texto: string) => el('li', { class: `marco ${classe}` }, texto)
  const grupos = agrupar(v.eventos)
  const n = v.norma
  if (n.data) {
    const li = el('li', { class: 'evento origem' })
    li.append(el('span', { class: 'quando' }, fmtData(n.data)), el('span', { class: 'oque' }, t('norma.publicada')))
    ol.append(li)
  }
  let marcouData = false
  let marcouHoje = false
  for (const g of grupos) {
    if (g.data && !marcouData && g.data > v.data) {
      ol.append(marcador('data', t('norma.marcoData', { data: fmtData(v.data) })))
      marcouData = true
    }
    if (g.data && !marcouHoje && g.data > hoje) {
      ol.append(marcador('hoje', t('norma.marcoHoje')))
      marcouHoje = true
    }
    const futuro = g.data !== null && g.data > hoje
    const li = el('li', { class: `evento ${g.eventos[0].aplicado === false ? 'posterior' : ''} ${g.data === null ? 'sem-data' : ''}` })
    const quando = el('button', { type: 'button', class: 'quando', title: t('norma.verNessaData') }, g.data ? fmtData(g.data) : t('norma.semData'))
    if (g.data) quando.addEventListener('click', () => onData(g.data!))
    else quando.setAttribute('disabled', '')
    li.append(quando)
    const corpo = el('div', { class: 'oque' })
    const cab = el('div')
    if (g.por) cab.append(el('a', { href: linkNorma(g.por.id) }, g.por.titulo ?? g.por.id))
    else cab.append(document.createTextNode(t('norma.normaDesconhecida')))
    if (futuro) cab.append(el('span', { class: 'selo futuro' }, t('norma.futuro')))
    if (g.eventos[0].origem_data === 'data_da_norma') cab.append(el('span', { class: 'contagem' }, t('norma.dataDaNorma')))
    corpo.append(cab)
    const tipos = new Map<string, number>()
    for (const e of g.eventos) tipos.set(e.tipo, (tipos.get(e.tipo) ?? 0) + 1)
    const resumo = [...tipos].map(([tp, k]) => `${tipoEvento(tp as EventoVigencia['tipo'])}${k > 1 ? ` (${fmt.format(k)})` : ''}`).join(' · ')
    if (g.eventos.length <= 3) {
      for (const e of g.eventos) {
        const linha = el('div', { class: 'alvo' })
        linha.append(document.createTextNode(`${tipoEvento(e.tipo)}: `), alvo(e))
        corpo.append(linha)
      }
    } else {
      const det = el('details')
      det.append(el('summary', {}, resumo))
      for (const e of g.eventos) {
        const linha = el('div', { class: 'alvo' })
        linha.append(document.createTextNode(`${tipoEvento(e.tipo)}: `), alvo(e))
        det.append(linha)
      }
      corpo.append(det)
    }
    li.append(corpo)
    ol.append(li)
  }
  if (!marcouData) ol.append(marcador('data', t('norma.marcoData', { data: fmtData(v.data) })))
  if (!marcouHoje && v.data !== hoje) ol.append(marcador('hoje', t('norma.marcoHoje')))
  if (!grupos.length) sec.append(el('p', { class: 'nota' }, t('norma.semEventos')))
  sec.append(ol)
  return sec
}

// ---------------------------------------------------------------- neighborhood graph

interface Grafo {
  destruir(): void
}

async function grafoVizinhanca(alvo: HTMLElement, sub: Subgrafo): Promise<Grafo> {
  const [{ default: cytoscape }, { default: dagre }] = await Promise.all([import('cytoscape'), import('cytoscape-dagre')])
  cytoscape.use(dagre)
  const datas = new Map(sub.nos.map((n) => [n.norma.id, n.norma.data]))
  const elementos: cytoscape.ElementDefinition[] = []
  for (const n of sub.nos) {
    const nr = n.norma
    elementos.push({
      data: {
        id: nr.id,
        rotulo: nr.titulo ?? nr.id,
        cor: token(GRUPO_VAR[n.grupo] ?? '--grupo-outros'),
        estado: nr.externo ? 'externa' : (nr.estado ?? ''),
        origem: n.distancia === 0 ? 1 : 0,
        data: nr.data,
      },
    })
  }
  for (const [i, a] of sub.arestas.entries()) {
    // layout edges point from the older norm to the newer one, so dagre puts older norms on the left; the arrow
    // still points the way the relation goes
    const dDe = datas.get(a.de) ?? ''
    const dPara = datas.get(a.para) ?? ''
    const inverter = Boolean(dDe && dPara && dDe > dPara)
    elementos.push({
      data: {
        id: `e${i}`,
        source: inverter ? a.para : a.de,
        target: inverter ? a.de : a.para,
        tipo: a.tipo,
        inverter: inverter ? 1 : 0,
        de: a.de,
        para: a.para,
        desde: a.desde,
      },
    })
  }
  const tinta = token('--text-secondary')
  const linha = token('--axis')
  const superficie = token('--surface-1')
  const cy = cytoscape({
    container: alvo,
    elements: elementos,
    wheelSensitivity: 0.2,
    minZoom: 0.2,
    maxZoom: 3,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(cor)',
          width: 14,
          height: 14,
          label: 'data(rotulo)',
          'font-size': 10,
          color: tinta,
          'text-valign': 'bottom',
          'text-margin-y': 4,
          'text-wrap': 'ellipsis',
          'text-max-width': '120px',
          'border-width': 2,
          'border-color': superficie,
        },
      },
      { selector: 'node[origem = 1]', style: { width: 24, height: 24, 'font-weight': 'bold', 'border-color': token('--text-primary') } },
      { selector: 'node[estado = "revogada"]', style: { 'background-opacity': 0.35 } },
      { selector: 'node[estado = "externa"]', style: { shape: 'round-rectangle' } },
      {
        selector: 'edge',
        style: {
          width: 1,
          'line-color': linha,
          'curve-style': 'bezier',
          'arrow-scale': 0.8,
          'target-arrow-color': linha,
          'source-arrow-color': linha,
        },
      },
      { selector: 'edge[inverter = 0]', style: { 'target-arrow-shape': 'triangle' } },
      { selector: 'edge[inverter = 1]', style: { 'source-arrow-shape': 'triangle' } },
      ...Object.entries(LINHA).map(([tipo, l]) => ({
        selector: `edge[tipo = "${tipo}"]`,
        style: { 'line-style': l.estilo, width: l.largura },
      })),
      { selector: '.apagado', style: { opacity: 0.15 } },
    ] as cytoscape.StylesheetJson,
    layout: { name: 'dagre', rankDir: 'LR', nodeSep: 18, rankSep: 70, animate: false } as cytoscape.LayoutOptions,
  })
  cy.on('mouseover', 'node', (e) => {
    const n = e.target
    const viz = n.closedNeighborhood()
    cy.elements().not(viz).addClass('apagado')
    const est = estadoRotulo(n.data('estado'))
    const pos = e.originalEvent as MouseEvent
    mostrarDica(pos.clientX, pos.clientY, n.data('rotulo'), `${est}${n.data('data') ? ` · ${fmtData(n.data('data'))}` : ''}`, n.id())
  })
  cy.on('mouseout', 'node', () => {
    cy.elements().removeClass('apagado')
    esconderDica()
  })
  cy.on('mouseover', 'edge', (e) => {
    const a = e.target
    const pos = e.originalEvent as MouseEvent
    const de = cy.getElementById(a.data('de')).data('rotulo')
    const para = cy.getElementById(a.data('para')).data('rotulo')
    const desde = a.data('desde') ? ` · ${t('visao.aPartirDe', { data: fmtData(a.data('desde')) })}` : ''
    mostrarDica(pos.clientX, pos.clientY, tDinamico(`relacao.${a.data('tipo')}`, a.data('tipo')), `${de} → ${para}${desde}`)
  })
  cy.on('mouseout', 'edge', esconderDica)
  cy.on('tap', 'node', (e) => {
    esconderDica()
    if (e.target.data('origem') !== 1) location.hash = linkNorma(e.target.id())
  })
  return { destruir: () => cy.destroy() }
}

function secaoGrafo(id: string): { sec: HTMLElement; destruir: () => void } {
  const sec = el('section', { class: 'cartao vizinhanca' })
  sec.append(el('h2', {}, t('norma.vizinhanca')))
  sec.append(el('p', { class: 'sub' }, t('norma.vizinhancaSub')))
  const controles = el('div', { class: 'filtros compacto' })
  const caixa = el('div', { class: 'cy' })
  const status = el('p', { class: 'nota' })
  const legenda = el('div', { class: 'legenda' })
  sec.append(controles, caixa, status, legenda)
  let profundidade = 1
  const tipos = new Set(TIPOS_RELACAO)
  let grafo: Grafo | undefined
  let pedido = 0

  for (const [tipo, l] of Object.entries(LINHA)) {
    const item = el('span', { class: 'item' })
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('width', '22')
    svg.setAttribute('height', '8')
    const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line')
    for (const [k, v] of Object.entries({ x1: 0, y1: 4, x2: 22, y2: 4, 'stroke-width': l.largura })) ln.setAttribute(k, String(v))
    ln.setAttribute('stroke', 'currentColor')
    if (l.estilo === 'dashed') ln.setAttribute('stroke-dasharray', '5 3')
    if (l.estilo === 'dotted') ln.setAttribute('stroke-dasharray', '1.5 2.5')
    svg.append(ln)
    item.append(svg, document.createTextNode(tDinamico(`relacao.${tipo}`, tipo)))
    legenda.append(item)
  }
  for (const g of Object.keys(GRUPO_VAR)) {
    const item = el('span', { class: 'item' })
    const amostra = el('span', { class: 'amostra' })
    amostra.style.background = `var(${GRUPO_VAR[g]})`
    amostra.style.borderRadius = '50%'
    item.append(amostra, document.createTextNode(tDinamico(`grupo.${g}`, g)))
    legenda.append(item)
  }

  async function desenhar(): Promise<void> {
    const meu = ++pedido
    caixa.classList.add('carregando')
    let sub: Subgrafo
    try {
      sub = await api.relacoes(id, profundidade, [...tipos])
    } catch (err) {
      status.textContent = err instanceof Error ? err.message : String(err)
      caixa.classList.remove('carregando')
      return
    }
    if (meu !== pedido) return
    grafo?.destruir()
    caixa.replaceChildren()
    caixa.classList.remove('carregando')
    grafo = await grafoVizinhanca(caixa, sub)
    status.textContent = t(sub.truncado ? 'norma.vizinhancaTruncada' : 'norma.vizinhancaStatus', {
      normas: fmt.format(sub.nos.length - 1),
      relacoes: fmt.format(sub.arestas.length),
    })
  }

  const prof = el('fieldset')
  prof.append(el('legend', {}, t('norma.saltos')))
  for (const p of [1, 2]) {
    const lab = el('label', { class: 'chip' })
    const r = el('input', { type: 'radio', name: 'saltos', value: String(p) })
    r.checked = p === profundidade
    r.addEventListener('change', () => {
      profundidade = p
      void desenhar()
    })
    lab.append(r, document.createTextNode(String(p)))
    prof.append(lab)
  }
  const tiposFs = el('fieldset')
  tiposFs.append(el('legend', {}, t('visao.filtroRelacao')))
  for (const tipo of TIPOS_RELACAO) {
    const lab = el('label', { class: 'chip' })
    const cb = el('input', { type: 'checkbox' })
    cb.checked = true
    cb.addEventListener('change', () => {
      if (cb.checked) tipos.add(tipo)
      else tipos.delete(tipo)
      if (tipos.size) void desenhar()
    })
    lab.append(cb, document.createTextNode(tDinamico(`relacao.${tipo}`, tipo)))
    tiposFs.append(lab)
  }
  controles.append(prof, tiposFs)
  void desenhar()
  const aoTema = () => void desenhar()
  window.addEventListener('regteia:tema', aoTema)
  return {
    sec,
    destruir: () => {
      pedido++
      window.removeEventListener('regteia:tema', aoTema)
      grafo?.destruir()
    },
  }
}

// ---------------------------------------------------------------- page

export async function paginaNorma(main: HTMLElement, ref: string, dataInicial?: string): Promise<() => void> {
  main.replaceChildren(el('p', { class: 'nota carregando-pagina' }, t('norma.carregando')))
  let detalhe: NormaDetalhe
  let texto: TextoNorma
  try {
    ;[detalhe, texto] = await Promise.all([api.norma(ref, 12), api.texto(ref)])
  } catch (err) {
    const caixa = el('div', { class: 'erro' })
    caixa.append(el('p', {}, err instanceof Error ? err.message : String(err)))
    const det = err instanceof ErroApi ? (err.detalhe as { sugestoes?: { id: string; titulo: string }[] }) : undefined
    for (const s of det?.sugestoes ?? []) caixa.append(el('div'), el('a', { href: linkNorma(s.id) }, s.titulo ?? s.id))
    main.replaceChildren(caixa)
    return () => {}
  }
  const n = detalhe.norma
  document.title = `${n.titulo ?? n.id} · Regteia`
  const porId = new Map(texto.dispositivos.map((d) => [d.id, d]))

  const pagina = el('div', { class: 'pagina-norma' })
  const barra = el('div', { class: 'filtros barra-data' })
  const corpo = el('div', { class: 'corpo-norma' })
  const coluna = el('div', { class: 'coluna-texto' })
  const lateral = el('div', { class: 'coluna-lateral' })
  corpo.append(coluna, lateral)
  pagina.append(cabecalho(detalhe), barra, corpo)
  main.replaceChildren(pagina)
  // in-page anchors (#d-art-88) would otherwise reach the hash router and leave the page
  pagina.addEventListener('click', (e) => {
    const a = (e.target as Element).closest<HTMLAnchorElement>('a[href^="#d-"]')
    if (!a) return
    e.preventDefault()
    document.getElementById(a.getAttribute('href')!.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })

  const g = secaoGrafo(n.id)
  const tempo = el('div')
  lateral.append(g.sec, tempo)

  // date switch
  const rotulo = el('label', { class: 'campo-data' })
  const entrada = el('input', { type: 'date' })
  entrada.value = dataInicial ?? hojeISO()
  rotulo.append(document.createTextNode(`${t('norma.emVigorEm')} `), entrada)
  const botaoHoje = el('button', { type: 'button', class: 'botao-fantasma' }, t('norma.hoje'))
  const situacao = el('div', { class: 'situacao-data' })
  barra.append(rotulo, botaoHoje, situacao)

  let pedido = 0
  async function aplicar(iso: string): Promise<void> {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return
    const meu = ++pedido
    corpo.classList.add('carregando')
    let v: VigenciaNorma
    try {
      v = await api.vigencia(n.id, iso)
    } catch (err) {
      corpo.classList.remove('carregando')
      situacao.replaceChildren(el('span', { class: 'erro' }, err instanceof Error ? err.message : String(err)))
      return
    }
    if (meu !== pedido) return
    corpo.classList.remove('carregando')
    const alvoHash = `#/norma/${encodeURIComponent(n.id)}${iso === hojeISO() ? '' : `?data=${iso}`}`
    if (location.hash !== alvoHash) history.replaceState(null, '', alvoHash)

    situacao.replaceChildren(el('span', { class: `selo ${v.situacao}` }, situacaoRotulo(v.situacao)), el('span', {}, v.motivo))
    coluna.replaceChildren()
    for (const nota of v.notas) coluna.append(el('p', { class: 'nota' }, `⚠ ${nota}`))
    if (texto.divisao === 'vazio') coluna.append(el('p', { class: 'nota' }, t('norma.semTexto')))
    if (n.externo) coluna.append(el('p', { class: 'nota' }, t('norma.externa')))
    if (v.dispositivos.length) coluna.append(sumario(v))
    for (const d of v.dispositivos) coluna.append(artigo(d, porId.get(d.id), iso))
    coluna.append(el('p', { class: 'nota' }, aviso(v.aviso)))
    tempo.replaceChildren(linhaDoTempo(v, (outra) => {
      entrada.value = outra
      void aplicar(outra)
    }))
  }
  entrada.addEventListener('change', () => void aplicar(entrada.value))
  botaoHoje.addEventListener('click', () => {
    entrada.value = hojeISO()
    void aplicar(entrada.value)
  })
  await aplicar(entrada.value)
  return () => {
    pedido++
    g.destruir()
    esconderDica()
  }
}
