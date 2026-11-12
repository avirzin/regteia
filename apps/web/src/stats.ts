// Statistics dashboard: coverage and health of the corpus, all from GET /api/estatisticas (computed live).
import { api, fmt, type Estatisticas } from './api'
import { barras, colunas, el, empilhadas, tabelaSimples, type Linha } from './charts'

const SERIES: Record<string, string> = {
  'bcb:comunicado': 'Comunicado (BCB)',
  'bcb:resolucao-cmn': 'Resolução CMN',
  'bcb:carta-circular': 'Carta Circular',
  'bcb:circular': 'Circular',
  'bcb:ato-do-presidente': 'Ato do Presidente',
  'bcb:instrucao-normativa-bcb': 'Instrução Normativa BCB',
  'bcb:ato-de-diretor': 'Ato de Diretor',
  'bcb:resolucao-bcb': 'Resolução BCB',
  'cvm:deliberacao': 'Deliberação CVM',
  'cvm:instrucao': 'Instrução CVM',
  'cvm:resolucao': 'Resolução CVM',
  'cvm:nota-explicativa': 'Nota Explicativa CVM',
  'cvm:portaria': 'Portaria CVM',
  'cvm:parecer-de-orientacao': 'Parecer de Orientação CVM',
  'cvm:oficio-circular-sin': 'Ofício-Circular CVM/SIN',
  'cvm:oficio-circular-sep': 'Ofício-Circular CVM/SEP',
  'cvm:oficio-circular-sre': 'Ofício-Circular CVM/SRE',
  'cvm:oficio-circular-smi': 'Ofício-Circular CVM/SMI',
  'bcb:ato-normativo-conjunto': 'Ato Normativo Conjunto',
  'bcb:resolucao-conjunta': 'Resolução Conjunta',
}
const RELACOES: Record<string, string> = {
  CITA: 'Cita',
  REGULAMENTA: 'Regulamenta (base legal)',
  REVOGA: 'Revoga',
  ALTERA: 'Altera',
  REVOGA_PARCIAL: 'Revoga parcialmente',
  CONJUNTA: 'Conjunta',
}
const PREFIXOS: Record<string, string> = {
  ext: 'Outros órgãos (ext)',
  lei: 'Leis ordinárias',
  dec: 'Decretos',
  mpv: 'Medidas provisórias',
  del: 'Decretos-lei',
  lcp: 'Leis complementares',
  ldl: 'Leis delegadas',
  bcb: 'BCB sem arquivo',
  cvm: 'CVM sem arquivo',
}

function cartao(titulo: string, sub: string, largo = false): [HTMLElement, HTMLElement] {
  const c = el('section', { class: largo ? 'cartao largo' : 'cartao' })
  const corpo = el('div')
  c.append(el('h2', {}, titulo), el('p', { class: 'sub' }, sub), corpo)
  return [c, corpo]
}

function kpi(rotulo: string, valor: number, heroi = false): HTMLElement {
  const d = el('div', { class: heroi ? 'heroi' : 'kpi' })
  d.append(el('div', { class: 'valor' }, fmt.format(valor)), el('div', { class: 'rotulo' }, rotulo))
  return d
}

function desenhar(raiz: HTMLElement, e: Estatisticas): void {
  const graficos: (() => void)[] = []
  raiz.replaceChildren()

  const [cKpi, kpis] = cartao('Acervo', 'Normas com arquivo nos acervos normas-bcb e normas-cvm.', true)
  kpis.className = 'kpis'
  kpis.append(
    kpi('normas', e.normas, true),
    kpi('vigentes', e.por_estado.vigente ?? 0),
    kpi('alteradas (texto consolidado)', e.por_estado.alterada ?? 0),
    kpi('revogadas', e.por_estado.revogada ?? 0),
    kpi('relações entre normas', e.arestas),
    kpi('normas referenciadas fora do acervo', e.stubs),
    kpi('referências não resolvidas', e.nao_resolvidos),
    kpi('textos obtidos por OCR', e.ocr),
  )
  raiz.append(cKpi)

  const partes = [
    { chave: 'vigente', rotulo: 'Vigente', cor: 'var(--estado-vigente)' },
    { chave: 'alterada', rotulo: 'Alterada', cor: 'var(--estado-alterada)' },
    { chave: 'revogada', rotulo: 'Revogada', cor: 'var(--estado-revogada)' },
  ]
  const [cOrg, org] = cartao('Situação por órgão', 'Estado atual de cada norma, segundo o grafo do acervo.', true)
  raiz.append(cOrg)
  const linhasOrg = Object.entries(e.por_orgao)
    .map(([rotulo, partes]) => ({ rotulo, partes }))
    .sort((a, b) => Object.values(b.partes).reduce((x, y) => x + y, 0) - Object.values(a.partes).reduce((x, y) => x + y, 0))
  graficos.push(() => empilhadas(org, linhasOrg, partes))

  const [cSer, ser] = cartao(
    'Normas por série',
    'As 15 maiores séries. Comunicados do BCB são, em sua maioria, avisos de leilão.',
  )
  raiz.append(cSer)
  const todas: Linha[] = e.por_serie.map((s) => {
    const chave = `${s.acervo}:${s.serie}`
    return {
      rotulo: SERIES[chave] ?? chave,
      valor: s.total,
      extra: `vigentes ${fmt.format(s.vigente)} · alteradas ${fmt.format(s.alterada)} · revogadas ${fmt.format(s.revogada)}`,
    }
  })
  const top = todas.slice(0, 15)
  const resto = todas.slice(15)
  if (resto.length) top.push({ rotulo: `Demais ${resto.length} séries`, valor: resto.reduce((a, l) => a + l.valor, 0) })
  graficos.push(() => barras(ser, top, { tabelaLinhas: todas, cabecalho: ['Série', 'Normas'] }))

  const [cDec, dec] = cartao('Normas por década', 'Pela data de cada norma. Todos os órgãos.')
  raiz.append(cDec)
  const porDecada = new Map<number, number>()
  for (const d of e.por_decada) porDecada.set(d.decada, (porDecada.get(d.decada) ?? 0) + d.n)
  const linhasDec = [...porDecada.entries()].sort((a, b) => a[0] - b[0]).map(([d, n]) => ({ rotulo: `${d}s`, valor: n }))
  graficos.push(() => colunas(dec, linhasDec, { cabecalho: ['Década', 'Normas'] }))

  const [cRel, rel] = cartao(
    'Relações por tipo',
    `${fmt.format(e.arestas_com_desde)} de ${fmt.format(e.arestas)} relações têm data de início (“desde”).`,
  )
  raiz.append(cRel)
  const linhasRel = Object.entries(e.arestas_por_relacao).map(([k, v]) => ({ rotulo: RELACOES[k] ?? k, valor: v }))
  graficos.push(() => barras(rel, linhasRel, { cabecalho: ['Relação', 'Relações'] }))

  const [cFon, fon] = cartao('Relações por origem', 'Campo do cabeçalho de onde o acervo extraiu cada relação.')
  raiz.append(cFon)
  const linhasFon = Object.entries(e.arestas_por_fonte).map(([k, v]) => ({ rotulo: k.replaceAll('+', ' + '), valor: v }))
  graficos.push(() => barras(fon, linhasFon, { rotuloLargura: 230, cabecalho: ['Origem', 'Relações'] }))

  const [cStub, stub] = cartao(
    'Normas fora do acervo',
    'Referenciadas por normas do acervo, mas sem texto aqui (leis federais chegam no passo 9 do roadmap).',
  )
  raiz.append(cStub)
  const linhasStub = Object.entries(e.stubs_por_prefixo).map(([k, v]) => ({ rotulo: PREFIXOS[k] ?? k, valor: v }))
  graficos.push(() => barras(stub, linhasStub, { cabecalho: ['Tipo', 'Normas'] }))

  const [cNr, nr] = cartao(
    'Referências não resolvidas',
    'O acervo não conseguiu ligar estas referências a uma norma. “alvo”: identificador sem norma; “padrão”: texto não reconhecido.',
  )
  raiz.append(cNr)
  const linhasNr = e.nao_resolvidos_detalhe.map((x) => ({
    rotulo: `${x.upstream.replace('normas-', '').toUpperCase()} · ${x.campo.replace('_', ' ')} · ${x.tipo}`,
    valor: x.n,
    extra: `${fmt.format(x.ocorrencias)} ocorrências`,
  }))
  graficos.push(() => barras(nr, linhasNr, { rotuloLargura: 260, cabecalho: ['Origem', 'Referências'] }))

  const [cIng, ing] = cartao('Última ingestão', 'Versão exata dos acervos carregada no banco. Atualizada a cada hora.', true)
  raiz.append(cIng)
  ing.append(
    tabelaSimples(
      ['Acervo', 'Commit', 'Quando', 'Modo', 'Arquivos'],
      e.ingestoes.map((i) => {
        const code = el('code', {}, i.sha ? i.sha.slice(0, 12) : '-')
        if (i.sha) code.title = i.sha
        const quando = i.em ? new Date(i.em).toLocaleString('pt-BR') : '-'
        return [i.fonte, code, quando, i.modo ?? '-', i.arquivos ?? 0]
      }),
    ),
    el(
      'p',
      { class: 'sub' },
      e.falhas_atualizacoes === null
        ? 'Falhas do parser de atualizações: o parser ainda não existe (roadmap, passo 7).'
        : `Falhas do parser de atualizações: ${fmt.format(e.falhas_atualizacoes)}`,
    ),
  )

  const render = () => graficos.forEach((g) => g())
  render()
  let t = 0
  new ResizeObserver(() => {
    clearTimeout(t)
    t = window.setTimeout(render, 120)
  }).observe(raiz)
}

export async function paginaEstatisticas(main: HTMLElement): Promise<void> {
  const raiz = el('div', { class: 'painel-est carregando' })
  main.replaceChildren(raiz)
  try {
    const e = await api.estatisticas()
    raiz.classList.remove('carregando')
    desenhar(raiz, e)
  } catch (err) {
    raiz.replaceChildren(el('p', { class: 'erro' }, `Não foi possível carregar as estatísticas: ${String(err)}`))
  }
}
