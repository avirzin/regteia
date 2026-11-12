// UI localization. Strings live in src/locales/<idioma>.json; to add a language, copy pt-BR.json, translate the
// values (keep keys and {placeholders}) and add it to DICIONARIOS and IDIOMAS below. The compiler fails if a file
// is missing a key or has one the others don't.
//
// Only the interface is translated. Data from the corpus (titles, ementas, series names, upstream notes, API
// messages) stays as published, in Portuguese.
import en from './locales/en.json'
import ptBR from './locales/pt-BR.json'

type Dicionario = typeof ptBR
type Caminhos<T, P extends string = ''> = {
  [K in keyof T & string]: T[K] extends string ? `${P}${K}` : Caminhos<T[K], `${P}${K}.`>
}[keyof T & string]
export type Chave = Caminhos<Dicionario>

const DICIONARIOS = {
  'pt-BR': ptBR satisfies typeof en,
  en: en satisfies Dicionario,
}
export type Idioma = keyof typeof DICIONARIOS
export const IDIOMAS = Object.keys(DICIONARIOS) as Idioma[]
const INTL: Record<Idioma, string> = { 'pt-BR': 'pt-BR', en: 'en-US' }
// Dates spelled so they can't be misread across conventions: 10/11/2025 in pt-BR, Nov 10, 2025 in English.
const DATA: Record<Idioma, Intl.DateTimeFormatOptions> = {
  'pt-BR': { day: '2-digit', month: '2-digit', year: 'numeric' },
  en: { dateStyle: 'medium' },
}
const ARMAZENADO = 'regteia-idioma'

function inicial(): Idioma {
  const salvo = localStorage.getItem(ARMAZENADO)
  if (salvo && salvo in DICIONARIOS) return salvo as Idioma
  return navigator.language.toLowerCase().startsWith('pt') ? 'pt-BR' : 'en'
}

let atual: Idioma = inicial()
let numero = new Intl.NumberFormat(INTL[atual])
let compacto = new Intl.NumberFormat(INTL[atual], { notation: 'compact', maximumFractionDigits: 1 })

export const idioma = (): Idioma => atual
export const localeIntl = (): string => INTL[atual]

function buscar(d: unknown, chave: string): string | undefined {
  let v = d
  for (const parte of chave.split('.')) {
    if (typeof v !== 'object' || v === null) return undefined
    v = (v as Record<string, unknown>)[parte]
  }
  return typeof v === 'string' ? v : undefined
}

function interpolar(s: string, params?: Record<string, string | number>): string {
  if (!params) return s
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m))
}

/** Translate a known key. Numbers in params are inserted as given; format them with fmt first. */
export function t(chave: Chave, params?: Record<string, string | number>): string {
  return interpolar(buscar(DICIONARIOS[atual], chave) ?? chave, params)
}

/** Translate a key built at runtime (e.g. `estado.${x}`); falls back when the key doesn't exist. */
export function tDinamico(chave: string, reserva: string, params?: Record<string, string | number>): string {
  return interpolar(buscar(DICIONARIOS[atual], chave) ?? reserva, params)
}

export const fmt = { format: (n: number) => numero.format(n) }
export const fmtCompacto = { format: (n: number) => compacto.format(n) }
export function fmtData(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat(INTL[atual], { ...DATA[atual], timeZone: 'UTC' }).format(d)
}
export function fmtDataHora(iso: string): string {
  return new Date(iso).toLocaleString(INTL[atual])
}

/** Static text in index.html: elements carry data-i18n (textContent) or data-i18n-<attr> (that attribute). */
function traduzirDocumento(): void {
  document.documentElement.lang = atual
  document.querySelectorAll<HTMLElement>('*').forEach((e) => {
    for (const [k, v] of Object.entries(e.dataset)) {
      if (!v) continue
      if (k === 'i18n') e.textContent = t(v as Chave)
      else if (k.startsWith('i18n')) {
        const attr = k.slice(4).replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`).replace(/^-/, '')
        e.setAttribute(attr, t(v as Chave))
      }
    }
  })
  document.querySelectorAll<HTMLButtonElement>('[data-idioma]').forEach((b) => {
    b.setAttribute('aria-pressed', String(b.dataset.idioma === atual))
  })
}

export function definirIdioma(novo: Idioma): void {
  if (novo === atual) return
  atual = novo
  numero = new Intl.NumberFormat(INTL[atual])
  compacto = new Intl.NumberFormat(INTL[atual], { notation: 'compact', maximumFractionDigits: 1 })
  localStorage.setItem(ARMAZENADO, novo)
  traduzirDocumento()
  window.dispatchEvent(new Event('regteia:idioma'))
}

export function iniciarIdioma(): void {
  traduzirDocumento()
  document.querySelectorAll<HTMLButtonElement>('[data-idioma]').forEach((b) => {
    b.addEventListener('click', () => definirIdioma(b.dataset.idioma as Idioma))
  })
}
