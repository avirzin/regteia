// Overview: the whole graph in cosmos.gl, colored by issuing body. Data: GET /api/grafo.arrow (nodes + edges).
// Filters keep the layout stable: hidden norms get size 0 and their links go transparent. Changing the language
// rebuilds the text (filters, legend, panel) in place, without restarting the layout.
import { Graph, PointShape } from '@cosmos.gl/graph'
import type { Table } from 'apache-arrow'
import { api, ErroApi, type NormaDetalhe } from './api'
import { el, esconderDica, mostrarDica } from './charts'
import { fmt, fmtData, idioma, t, tDinamico } from './i18n'

const GRUPO_VAR = ['--grupo-cmn', '--grupo-bcb', '--grupo-cvm', '--grupo-lei', '--grupo-outros']
const GRUPO_FORMA = [PointShape.Circle, PointShape.Circle, PointShape.Circle, PointShape.Square, PointShape.Diamond]
const estadoRotulo = (e: string) => tDinamico(`estado.${e}`, e)
const grupoRotulo = (g: string) => tDinamico(`grupo.${g}`, g)

function corRGBA(css: string): [number, number, number, number] {
  const ctx = document.createElement('canvas').getContext('2d')!
  ctx.fillStyle = css.trim()
  const v = ctx.fillStyle // "#rrggbb" or "rgba(r, g, b, a)"
  if (v.startsWith('#')) return [1, 3, 5].map((i) => parseInt(v.slice(i, i + 2), 16) / 255).concat(1) as [number, number, number, number]
  const [r, g, b, a] = v.replace(/[^\d.,]/g, '').split(',').map(Number)
  return [r / 255, g / 255, b / 255, a ?? 1]
}
const token = (nome: string) => getComputedStyle(document.documentElement).getPropertyValue(nome)

interface Dados {
  n: number
  ids: string[]
  titulos: (string | null)[]
  grupo: Uint8Array
  estado: Uint8Array
  ano: (number | null)[]
  links: Float32Array
  tipo: Uint8Array
  grau: Uint32Array
  grupos: string[]
  estados: string[]
  relacoes: string[]
  indice: Map<string, number>
}

function lerDados(nos: Table, arestas: Table): Dados {
  const meta = nos.schema.metadata
  const n = nos.numRows
  const ids = nos.getChild('id')!.toArray() as string[]
  const anoV = nos.getChild('ano')!
  const ano: (number | null)[] = new Array(n)
  for (let i = 0; i < n; i++) ano[i] = anoV.get(i)
  const origem = arestas.getChild('origem')!.toArray() as Uint32Array
  const destino = arestas.getChild('destino')!.toArray() as Uint32Array
  const links = new Float32Array(origem.length * 2)
  const grau = new Uint32Array(n)
  for (let i = 0; i < origem.length; i++) {
    links[2 * i] = origem[i]
    links[2 * i + 1] = destino[i]
    grau[origem[i]]++
    grau[destino[i]]++
  }
  return {
    n,
    ids,
    titulos: nos.getChild('titulo')!.toArray() as (string | null)[],
    grupo: nos.getChild('grupo')!.toArray() as Uint8Array,
    estado: nos.getChild('estado')!.toArray() as Uint8Array,
    ano,
    links,
    tipo: arestas.getChild('tipo')!.toArray() as Uint8Array,
    grau,
    grupos: JSON.parse(meta.get('grupos')!),
    estados: JSON.parse(meta.get('estados')!),
    relacoes: JSON.parse(meta.get('relacoes')!),
    indice: new Map(ids.map((id, i) => [id, i])),
  }
}

interface Filtro {
  grupos: Set<number>
  estados: Set<number>
  relacoes: Set<number>
  de: number
  ate: number
}

function chips(nome: string, itens: { rotulo: string; valor: number }[], atual: Set<number>, onChange: (s: Set<number>) => void): HTMLFieldSetElement {
  const fs = el('fieldset')
  fs.append(el('legend', {}, nome))
  const sel = new Set(atual)
  for (const it of itens) {
    const lab = el('label', { class: 'chip' })
    const cb = el('input', { type: 'checkbox' })
    cb.checked = sel.has(it.valor)
    cb.addEventListener('change', () => {
      if (cb.checked) sel.add(it.valor)
      else sel.delete(it.valor)
      onChange(sel)
    })
    lab.append(cb, document.createTextNode(it.rotulo))
    fs.append(lab)
  }
  return fs
}

function linkSeguro(href: string | null, texto: string): HTMLElement {
  if (!href || !/^https?:\/\//.test(href)) return el('span', {}, texto)
  return el('a', { href, target: '_blank', rel: 'noopener noreferrer' }, texto)
}

export async function paginaVisaoGeral(main: HTMLElement, comunicados = false): Promise<() => void> {
  const filtros = el('div', { class: 'filtros' })
  const visao = el('div', { class: 'visao carregando' })
  const canvasDiv = el('div')
  canvasDiv.style.cssText = 'position:absolute;inset:0'
  const legenda = el('div', { class: 'legenda-grafo' })
  const status = el('div', { class: 'status-grafo' }, t('visao.carregando'))
  const painel = el('aside', { class: 'painel' })
  painel.hidden = true
  visao.append(canvasDiv, legenda, status, painel)
  main.replaceChildren(filtros, visao)

  let dados: Dados
  try {
    const { nos, arestas } = await api.grafo(comunicados)
    dados = lerDados(nos, arestas)
  } catch (err) {
    visao.replaceChildren(el('p', { class: 'erro' }, t('visao.erro', { erro: String(err) })))
    return () => {}
  }

  const anos = dados.ano.filter((a): a is number => a !== null)
  const decadaMin = Math.floor(Math.min(...anos) / 10) * 10
  const decadaMax = Math.floor(Math.max(...anos) / 10) * 10
  const filtro: Filtro = {
    grupos: new Set(dados.grupos.map((_, i) => i)),
    estados: new Set(dados.estados.map((_, i) => i)),
    relacoes: new Set(dados.relacoes.map((_, i) => i)),
    de: decadaMin,
    ate: decadaMax,
  }

  const graph = new Graph(canvasDiv, {
    backgroundColor: token('--surface-1').trim(),
    pointDefaultSize: 3,
    pointSizeScale: 1,
    scalePointsOnZoom: true,
    renderLinks: true,
    linkDefaultWidth: 0.6,
    linkDefaultArrows: false,
    linkVisibilityDistanceRange: [50, 300],
    linkVisibilityMinTransparency: 0.15,
    curvedLinks: false,
    simulationRepulsion: 0.8,
    simulationLinkSpring: 0.4,
    simulationLinkDistance: 6,
    simulationGravity: 0.2,
    simulationFriction: 0.85,
    simulationDecay: 3000,
    fitViewOnInit: true,
    fitViewDelay: 2500,
    fitViewPadding: 0.1,
    enableDrag: true,
    hoveredPointCursor: 'pointer',
    renderHoveredPointRing: true,
    pointGreyoutOpacity: 0.12,
    linkGreyoutOpacity: 0.03,
    transitionDuration: 0,
    randomSeed: 42,
    onPointMouseOver: (i, _pos, ev) => {
      const e = ev as MouseEvent | undefined
      const est = estadoRotulo(dados.estados[dados.estado[i]])
      const ano = dados.ano[i] ? ` · ${dados.ano[i]}` : ''
      mostrarDica(e?.clientX ?? 0, e?.clientY ?? 0, dados.titulos[i] ?? dados.ids[i], `${est}${ano} · ${grupoRotulo(dados.grupos[dados.grupo[i]])}`, `${dados.ids[i]} · ${t('visao.dicaRelacoes', { n: fmt.format(dados.grau[i]) })}`)
    },
    onPointMouseOut: esconderDica,
    onPointClick: (i) => selecionar(i),
    onBackgroundClick: () => limparSelecao(),
    onSimulationEnd: () => graph.fitView(800, 0.1),
  })

  const visiveis = new Uint8Array(dados.n)
  function aplicarFiltro(): void {
    const sizes = new Float32Array(dados.n)
    const contagem = new Array(dados.grupos.length).fill(0)
    let nVis = 0
    for (let i = 0; i < dados.n; i++) {
      const a = dados.ano[i]
      const dec = a === null ? null : Math.floor(a / 10) * 10
      const ok =
        filtro.grupos.has(dados.grupo[i]) && filtro.estados.has(dados.estado[i]) && (dec === null || (dec >= filtro.de && dec <= filtro.ate))
      visiveis[i] = ok ? 1 : 0
      if (ok) {
        sizes[i] = Math.min(16, 1.5 + 1.1 * Math.log2(1 + dados.grau[i]))
        contagem[dados.grupo[i]]++
        nVis++
      }
    }
    const link = corRGBA(token('--link'))
    const cores = new Float32Array((dados.links.length / 2) * 4)
    let lVis = 0
    for (let j = 0; j < dados.links.length / 2; j++) {
      const ok = filtro.relacoes.has(dados.tipo[j]) && visiveis[dados.links[2 * j]] && visiveis[dados.links[2 * j + 1]]
      cores.set(ok ? link : [0, 0, 0, 0], j * 4)
      if (ok) lVis++
    }
    graph.setPointSizes(sizes)
    graph.setLinkColors(cores)
    graph.render()
    status.textContent = t('visao.status', { normas: fmt.format(nVis), relacoes: fmt.format(lVis) }) + (comunicados ? '' : ` · ${t('visao.comunicadosOcultos')}`)
    desenharLegenda(contagem)
  }

  function aplicarCores(): void {
    const paleta = GRUPO_VAR.map((v) => corRGBA(token(v)))
    const cores = new Float32Array(dados.n * 4)
    for (let i = 0; i < dados.n; i++) cores.set(paleta[dados.grupo[i]], i * 4)
    graph.setPointColors(cores)
    graph.setConfigPartial({ backgroundColor: token('--surface-1').trim() })
    aplicarFiltro()
  }

  function desenharLegenda(contagem: number[]): void {
    legenda.replaceChildren()
    dados.grupos.forEach((g, i) => {
      const linha = el('div', { class: 'linha' })
      const m = el('span', { class: `marca-ponto${GRUPO_FORMA[i] === PointShape.Circle ? '' : ' quadrado'}` })
      m.style.background = `var(${GRUPO_VAR[i]})`
      if (GRUPO_FORMA[i] === PointShape.Diamond) m.style.transform = 'rotate(45deg) scale(0.8)'
      linha.append(m, el('span', {}, grupoRotulo(g)), el('span', {}, fmt.format(contagem[i])))
      legenda.append(linha)
    })
    legenda.append(el('div', { class: 'linha sec' }, t('visao.legendaTamanho')))
  }

  let mostrada: string | null = null
  function limparSelecao(): void {
    painel.hidden = true
    mostrada = null
    graph.setConfigPartial({ highlightedPointIndices: undefined, highlightedLinkIndices: undefined, focusedPointIndex: undefined })
  }

  async function selecionar(i: number, zoom = false): Promise<void> {
    const vizinhos = graph.getNeighboringPointIndices(i)
    graph.setConfigPartial({
      highlightedPointIndices: [i, ...vizinhos],
      highlightedLinkIndices: graph.getConnectedLinkIndices(i),
      focusedPointIndex: i,
    })
    if (zoom) graph.zoomToPointByIndex(i, 700, 6)
    await mostrarPainel(dados.ids[i])
  }

  async function mostrarPainel(ref: string): Promise<void> {
    mostrada = ref
    painel.hidden = false
    painel.classList.add('carregando')
    let d: NormaDetalhe
    try {
      d = await api.norma(ref)
    } catch (err) {
      painel.classList.remove('carregando')
      const msg = err instanceof ErroApi ? err.message : String(err)
      painel.replaceChildren(el('p', { class: 'erro' }, msg))
      return
    }
    painel.classList.remove('carregando')
    const n = d.norma
    const fechar = el('button', { class: 'botao-fantasma fechar', type: 'button', 'aria-label': t('visao.fechar') }, '×')
    fechar.addEventListener('click', limparSelecao)
    const estado = n.externo ? 'externa' : (n.estado ?? '')
    const selo = el('span', { class: `selo ${estado}` }, estadoRotulo(estado))
    painel.replaceChildren(fechar, el('h2', {}, n.titulo ?? n.id))
    const meta = el('p', { class: 'nota' })
    meta.append(selo, document.createTextNode(`  ${n.id}${n.data ? ` · ${fmtData(n.data)}` : ''}`))
    painel.append(meta)
    const links = el('p')
    if (n.fonte_url) links.append(linkSeguro(n.fonte_url, t('visao.fonteOficial')))
    if (n.url_arquivo) links.append(document.createTextNode(' · '), linkSeguro(n.url_arquivo, t('visao.arquivo')))
    if (n.url_externa) links.append(linkSeguro(n.url_externa, t('visao.ondeEsta')))
    painel.append(links)
    if (n.ementa) painel.append(el('p', {}, n.ementa))
    if (d.sumario.length) {
      const artigos = d.sumario.filter((x) => x.tipo === 'artigo')
      const revogados = d.sumario.filter((x) => x.revogado).length
      const partes = [t('visao.painelDispositivos', { n: fmt.format(d.sumario.length) })]
      if (artigos.length) partes.push(t('visao.painelArtigos', { n: fmt.format(artigos.length) }))
      if (revogados) partes.push(t('visao.painelRevogados', { n: fmt.format(revogados) }))
      painel.append(el('p', { class: 'nota' }, partes.join(' · ')))
    }
    for (const nota of d.notas) painel.append(el('p', { class: 'nota' }, `⚠ ${nota}`))
    for (const g of d.relacoes) {
      painel.append(el('strong', {}, `${tDinamico(`direcao.${g.direcao}.${g.tipo}`, g.tipo)} (${fmt.format(g.total)})`))
      const ul = el('ul')
      for (const v of g.itens) {
        const li = el('li')
        const a = el('a', { href: '#' }, v.norma.titulo ?? v.norma.id)
        a.addEventListener('click', (e) => {
          e.preventDefault()
          const j = dados.indice.get(v.norma.id)
          if (j !== undefined) selecionar(j, true)
          else mostrarPainel(v.norma.id)
        })
        const est = estadoRotulo(v.norma.externo ? 'externa' : (v.norma.estado ?? '')).toLowerCase()
        li.append(a, document.createTextNode(` · ${est}${v.desde ? ` · ${t('visao.aPartirDe', { data: fmtData(v.desde) })}` : ''}`))
        ul.append(li)
      }
      if (g.total > g.itens.length) ul.append(el('li', { class: 'nota' }, t('visao.eMais', { n: fmt.format(g.total - g.itens.length) })))
      painel.append(ul)
    }
    // d.aviso is the API's disclaimer (Portuguese); other languages show the same text from the locale file.
    painel.append(el('p', { class: 'nota' }, idioma() === 'pt-BR' ? d.aviso : t('app.aviso')))
  }

  // ---- filter row (rebuilt from the current filter state when the language changes) ----
  const decadas: number[] = []
  for (let d = decadaMin; d <= decadaMax; d += 10) decadas.push(d)

  async function encontrar(ref: string): Promise<void> {
    try {
      const d = await api.norma(ref, 1)
      const j = dados.indice.get(d.norma.id)
      if (j !== undefined && visiveis[j]) selecionar(j, true)
      else mostrarPainel(d.norma.id)
    } catch (err) {
      painel.hidden = false
      mostrada = null
      const det = err instanceof ErroApi ? (err.detalhe as { sugestoes?: { id: string; titulo: string }[] }) : undefined
      painel.replaceChildren(el('p', { class: 'erro' }, err instanceof Error ? err.message : String(err)))
      for (const s of det?.sugestoes ?? []) {
        const a = el('a', { href: '#' }, s.titulo ?? s.id)
        a.addEventListener('click', (ev) => {
          ev.preventDefault()
          void encontrar(s.id)
        })
        painel.append(el('div'), a)
      }
    }
  }

  let textoBusca = ''
  function montarFiltros(): void {
    const busca = el('form')
    const entrada = el('input', { type: 'search', placeholder: t('visao.busca'), size: '36' })
    entrada.value = textoBusca
    entrada.addEventListener('input', () => (textoBusca = entrada.value))
    busca.append(entrada)
    busca.addEventListener('submit', (e) => {
      e.preventDefault()
      const ref = entrada.value.trim()
      if (ref) void encontrar(ref)
    })

    const selDe = el('select', { 'aria-label': t('visao.decadaInicial') })
    const selAte = el('select', { 'aria-label': t('visao.decadaFinal') })
    for (const d of decadas) {
      selDe.append(el('option', { value: String(d) }, t('visao.decada', { d })))
      selAte.append(el('option', { value: String(d) }, t('visao.decada', { d })))
    }
    selDe.value = String(filtro.de)
    selAte.value = String(filtro.ate)
    const onDecada = () => {
      filtro.de = Math.min(Number(selDe.value), Number(selAte.value))
      filtro.ate = Math.max(Number(selDe.value), Number(selAte.value))
      aplicarFiltro()
    }
    selDe.addEventListener('change', onDecada)
    selAte.addEventListener('change', onDecada)
    const fsDec = el('fieldset')
    fsDec.append(el('legend', {}, t('visao.decadas')), selDe, el('span', {}, t('visao.decadaAte')), selAte)

    const comLab = el('label', { class: 'chip' })
    const comCb = el('input', { type: 'checkbox' })
    comCb.checked = comunicados
    comLab.append(comCb, document.createTextNode(t('visao.incluirComunicados')))
    comCb.addEventListener('change', () => {
      window.dispatchEvent(new CustomEvent('regteia:comunicados', { detail: comCb.checked }))
    })

    filtros.replaceChildren(
      busca,
      chips(t('visao.filtroOrgao'), dados.grupos.map((g, i) => ({ rotulo: grupoRotulo(g), valor: i })), filtro.grupos, (s) => {
        filtro.grupos = s
        aplicarFiltro()
      }),
      chips(t('visao.filtroSituacao'), dados.estados.map((e, i) => ({ rotulo: estadoRotulo(e), valor: i })), filtro.estados, (s) => {
        filtro.estados = s
        aplicarFiltro()
      }),
      chips(t('visao.filtroRelacao'), dados.relacoes.map((r, i) => ({ rotulo: tDinamico(`relacao.${r}`, r), valor: i })), filtro.relacoes, (s) => {
        filtro.relacoes = s
        aplicarFiltro()
      }),
      fsDec,
      comLab,
    )
  }
  montarFiltros()

  // ---- data into the graph ----
  await graph.ready
  const pos = new Float32Array(dados.n * 2)
  let seed = 7
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647)
  for (let i = 0; i < dados.n * 2; i++) pos[i] = 2048 + (rnd() - 0.5) * 1600
  graph.setPointPositions(pos)
  graph.setLinks(dados.links)
  graph.setPointShapes(new Float32Array(dados.n).map((_, i) => GRUPO_FORMA[dados.grupo[i]]))
  aplicarCores()
  visao.classList.remove('carregando')

  const onTema = () => aplicarCores()
  const onIdioma = () => {
    montarFiltros()
    aplicarFiltro()
    if (!painel.hidden && mostrada) void mostrarPainel(mostrada)
  }
  window.addEventListener('regteia:tema', onTema)
  window.addEventListener('regteia:idioma', onIdioma)
  return () => {
    window.removeEventListener('regteia:tema', onTema)
    window.removeEventListener('regteia:idioma', onIdioma)
    esconderDica()
    graph.destroy()
  }
}
