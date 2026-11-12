// Statistics dashboard: coverage and health of the corpus, all from GET /api/estatisticas (computed live).
import { api, type Estatisticas } from './api'
import { fmt, fmtDataHora, t, tDinamico } from './i18n'
import { barras, colunas, el, empilhadas, tabelaSimples, type Linha } from './charts'

// Series names are the official instrument names: they stay in Portuguese in every language.
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

  const [cKpi, kpis] = cartao(t('est.acervo.titulo'), t('est.acervo.sub'), true)
  kpis.className = 'kpis'
  kpis.append(
    kpi(t('est.kpi.normas'), e.normas, true),
    kpi(t('est.kpi.vigentes'), e.por_estado.vigente ?? 0),
    kpi(t('est.kpi.alteradas'), e.por_estado.alterada ?? 0),
    kpi(t('est.kpi.revogadas'), e.por_estado.revogada ?? 0),
    kpi(t('est.kpi.relacoes'), e.arestas),
    kpi(t('est.kpi.stubs'), e.stubs),
    kpi(t('est.kpi.naoResolvidos'), e.nao_resolvidos),
    kpi(t('est.kpi.ocr'), e.ocr),
  )
  raiz.append(cKpi)

  const partes = [
    { chave: 'vigente', rotulo: t('est.estado.vigente'), cor: 'var(--estado-vigente)' },
    { chave: 'alterada', rotulo: t('est.estado.alterada'), cor: 'var(--estado-alterada)' },
    { chave: 'revogada', rotulo: t('est.estado.revogada'), cor: 'var(--estado-revogada)' },
  ]
  const [cOrg, org] = cartao(t('est.orgao.titulo'), t('est.orgao.sub'), true)
  raiz.append(cOrg)
  const linhasOrg = Object.entries(e.por_orgao)
    .map(([rotulo, partes]) => ({ rotulo, partes }))
    .sort((a, b) => Object.values(b.partes).reduce((x, y) => x + y, 0) - Object.values(a.partes).reduce((x, y) => x + y, 0))
  graficos.push(() => empilhadas(org, linhasOrg, partes))

  const [cSer, ser] = cartao(t('est.serie.titulo'), t('est.serie.sub'))
  raiz.append(cSer)
  const todas: Linha[] = e.por_serie.map((s) => {
    const chave = `${s.acervo}:${s.serie}`
    return {
      rotulo: SERIES[chave] ?? chave,
      valor: s.total,
      extra: t('est.serie.extra', { v: fmt.format(s.vigente), a: fmt.format(s.alterada), r: fmt.format(s.revogada) }),
    }
  })
  const top = todas.slice(0, 15)
  const resto = todas.slice(15)
  if (resto.length) top.push({ rotulo: t('est.serie.demais', { n: fmt.format(resto.length) }), valor: resto.reduce((a, l) => a + l.valor, 0) })
  graficos.push(() => barras(ser, top, { tabelaLinhas: todas, cabecalho: [t('est.serie.cabecalho'), t('graficos.normas')] }))

  const [cDec, dec] = cartao(t('est.decada.titulo'), t('est.decada.sub'))
  raiz.append(cDec)
  const porDecada = new Map<number, number>()
  for (const d of e.por_decada) porDecada.set(d.decada, (porDecada.get(d.decada) ?? 0) + d.n)
  const linhasDec = [...porDecada.entries()].sort((a, b) => a[0] - b[0]).map(([d, n]) => ({ rotulo: t('visao.decada', { d }), valor: n }))
  graficos.push(() => colunas(dec, linhasDec, { cabecalho: [t('est.decada.cabecalho'), t('graficos.normas')] }))

  const [cRel, rel] = cartao(
    t('est.relacao.titulo'),
    t('est.relacao.sub', { com: fmt.format(e.arestas_com_desde), total: fmt.format(e.arestas) }),
  )
  raiz.append(cRel)
  const linhasRel = Object.entries(e.arestas_por_relacao).map(([k, v]) => ({ rotulo: tDinamico(`est.relacao.${k}`, k), valor: v }))
  graficos.push(() => barras(rel, linhasRel, { cabecalho: [t('est.relacao.cabecalho'), t('est.relacao.valor')] }))

  const [cFon, fon] = cartao(t('est.fonte.titulo'), t('est.fonte.sub'))
  raiz.append(cFon)
  const linhasFon = Object.entries(e.arestas_por_fonte).map(([k, v]) => ({ rotulo: k.replaceAll('+', ' + '), valor: v }))
  graficos.push(() => barras(fon, linhasFon, { rotuloLargura: 230, cabecalho: [t('est.fonte.cabecalho'), t('est.relacao.valor')] }))

  const [cStub, stub] = cartao(t('est.stubs.titulo'), t('est.stubs.sub'))
  raiz.append(cStub)
  const linhasStub = Object.entries(e.stubs_por_prefixo).map(([k, v]) => ({ rotulo: tDinamico(`est.stubs.prefixo.${k}`, k), valor: v }))
  graficos.push(() => barras(stub, linhasStub, { cabecalho: [t('est.stubs.cabecalho'), t('graficos.normas')] }))

  const [cNr, nr] = cartao(t('est.naoResolvidos.titulo'), t('est.naoResolvidos.sub'))
  raiz.append(cNr)
  const linhasNr = e.nao_resolvidos_detalhe.map((x) => ({
    rotulo: `${x.upstream.replace('normas-', '').toUpperCase()} · ${x.campo.replace('_', ' ')} · ${tDinamico(`est.naoResolvidos.${x.tipo}`, x.tipo)}`,
    valor: x.n,
    extra: t('est.naoResolvidos.ocorrencias', { n: fmt.format(x.ocorrencias) }),
  }))
  graficos.push(() => barras(nr, linhasNr, { rotuloLargura: 260, cabecalho: [t('est.naoResolvidos.cabecalho'), t('est.naoResolvidos.valor')] }))

  const [cDisp, disp] = cartao(t('est.dispositivos.titulo'), t('est.dispositivos.sub'), true)
  raiz.append(cDisp)
  const kpisDisp = el('div', { class: 'kpis' })
  kpisDisp.append(
    kpi(t('est.dispositivos.kpiDispositivos'), e.dispositivos),
    kpi(t('est.dispositivos.kpiArtigos'), e.dispositivos_por_tipo.artigo ?? 0),
    kpi(t('est.dispositivos.kpiRevogados'), e.dispositivos_revogados),
    kpi(t('est.dispositivos.kpiAnteriores'), e.dispositivos_com_redacao_anterior),
  )
  const grade = el('div', { class: 'dupla' })
  const [divA, divB] = [el('div'), el('div')]
  grade.append(divA, divB)
  disp.append(kpisDisp, grade)
  const linhasDiv = Object.entries(e.normas_por_divisao).map(([k, v]) => ({
    rotulo: tDinamico(`est.dispositivos.divisao.${k}`, k),
    valor: v,
  }))
  const linhasTipo = Object.entries(e.dispositivos_por_tipo).map(([k, v]) => ({
    rotulo: tDinamico(`est.dispositivos.tipo.${k}`, k),
    valor: v,
  }))
  graficos.push(() => {
    divA.replaceChildren(el('h3', {}, t('est.dispositivos.porDivisao')), el('div'))
    divB.replaceChildren(el('h3', {}, t('est.dispositivos.porTipo')), el('div'))
    barras(divA.lastElementChild as HTMLElement, linhasDiv, {
      cabecalho: [t('est.dispositivos.cabecalhoDivisao'), t('graficos.normas')],
    })
    barras(divB.lastElementChild as HTMLElement, linhasTipo, {
      cabecalho: [t('est.dispositivos.cabecalhoTipo'), t('est.dispositivos.valor')],
    })
  })

  const [cIng, ing] = cartao(t('est.ingestao.titulo'), t('est.ingestao.sub'), true)
  raiz.append(cIng)
  ing.append(
    tabelaSimples(
      ['acervo', 'commit', 'quando', 'modo', 'arquivos'].map((k) => tDinamico(`est.ingestao.${k}`, k)),
      e.ingestoes.map((i) => {
        const code = el('code', {}, i.sha ? i.sha.slice(0, 12) : '-')
        if (i.sha) code.title = i.sha
        const quando = i.em ? fmtDataHora(i.em) : '-'
        return [i.fonte, code, quando, i.modo ?? '-', i.arquivos ?? 0]
      }),
    ),
    el(
      'p',
      { class: 'sub' },
      e.falhas_atualizacoes === null
        ? t('est.ingestao.semParser')
        : t('est.ingestao.falhas', { n: fmt.format(e.falhas_atualizacoes) }),
    ),
  )

  const render = () => graficos.forEach((g) => g())
  render()
  let espera = 0
  new ResizeObserver(() => {
    clearTimeout(espera)
    espera = window.setTimeout(render, 120)
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
    raiz.replaceChildren(el('p', { class: 'erro' }, t('est.erro', { erro: String(err) })))
  }
}
