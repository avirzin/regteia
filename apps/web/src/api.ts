// Typed client for regteia-server. Shapes mirror regteia_query.modelos.
import { tableFromIPC, type Table } from 'apache-arrow'
import { t } from './i18n'

export type Estado = 'vigente' | 'alterada' | 'revogada'

export interface NormaResumo {
  id: string
  externo: boolean
  acervo: string | null
  titulo: string | null
  tipo: string | null
  orgao: string | null
  data: string | null
  estado: Estado | null
  ementa: string | null
  fonte_url: string | null
  url_arquivo: string | null
  url_externa: string | null
  versao_texto: string | null
  ocr: boolean | null
}

export interface GrupoRelacoes {
  direcao: 'saida' | 'entrada'
  tipo: string
  total: number
  itens: { norma: NormaResumo; desde: string | null; fonte: string | null }[]
}

export interface DispositivoResumo {
  id: string
  tipo: string
  rotulo: string
  revogado: boolean
  contexto: string | null
}

export interface NormaDetalhe {
  norma: NormaResumo
  relacoes: GrupoRelacoes[]
  notas: string[]
  divisao: string | null
  sumario: DispositivoResumo[]
  aviso: string
}

export interface Estatisticas {
  normas: number
  stubs: number
  arestas: number
  nao_resolvidos: number
  ocr: number
  por_estado: Record<string, number>
  por_orgao: Record<string, Record<string, number>>
  por_serie: { acervo: string; serie: string; orgao: string; total: number; vigente: number; alterada: number; revogada: number }[]
  por_decada: { decada: number; orgao: string; n: number }[]
  arestas_por_relacao: Record<string, number>
  arestas_por_fonte: Record<string, number>
  arestas_com_desde: number
  stubs_por_prefixo: Record<string, number>
  nao_resolvidos_detalhe: { upstream: string; tipo: string; campo: string; n: number; ocorrencias: number }[]
  dispositivos: number
  dispositivos_por_tipo: Record<string, number>
  normas_por_divisao: Record<string, number>
  dispositivos_revogados: number
  dispositivos_com_redacao_anterior: number
  falhas_atualizacoes: number | null
  ingestoes: { fonte: string; sha: string | null; em: string | null; arquivos: number | null; modo: string | null }[]
  aviso: string
}

export class ErroApi extends Error {
  constructor(
    public status: number,
    public detalhe: unknown,
  ) {
    super(typeof detalhe === 'object' && detalhe && 'erro' in detalhe ? String(detalhe.erro) : `HTTP ${status}`)
  }
}

async function json<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new ErroApi(r.status, body.detail ?? body)
  }
  return r.json() as Promise<T>
}

export const api = {
  estatisticas: () => json<Estatisticas>('/api/estatisticas'),
  norma: (ref: string, limite = 8) => json<NormaDetalhe>(`/api/normas/${encodeURIComponent(ref)}?limite=${limite}`),
  async grafo(comunicados: boolean): Promise<{ nos: Table; arestas: Table }> {
    const q = comunicados ? '&comunicados=true' : ''
    const [nos, arestas] = await Promise.all(
      ['nos', 'arestas'].map(async (t) => {
        const r = await fetch(`/api/grafo.arrow?tabela=${t}${q}`)
        if (!r.ok) throw new ErroApi(r.status, null)
        return tableFromIPC(new Uint8Array(await r.arrayBuffer()))
      }),
    )
    if (nos.schema.metadata.get('versao') !== arestas.schema.metadata.get('versao')) {
      throw new Error(t('visao.grafoMudou'))
    }
    return { nos, arestas }
  },
}

export { fmt, fmtCompacto, fmtData } from './i18n'
