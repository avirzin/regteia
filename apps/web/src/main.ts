import './style.css'
import { paginaVisaoGeral } from './overview'
import { paginaEstatisticas } from './stats'

const main = document.getElementById('app')!
let desmontar: (() => void) | undefined
let comunicados = false

async function rota(): Promise<void> {
  desmontar?.()
  desmontar = undefined
  const pagina = location.hash.startsWith('#/estatisticas') ? 'estatisticas' : 'visao-geral'
  document.querySelectorAll<HTMLAnchorElement>('nav a').forEach((a) => {
    if (a.dataset.rota === pagina) a.setAttribute('aria-current', 'page')
    else a.removeAttribute('aria-current')
  })
  if (pagina === 'estatisticas') {
    document.title = 'Estatísticas · Regteia'
    await paginaEstatisticas(main)
  } else {
    document.title = 'Visão geral · Regteia'
    desmontar = await paginaVisaoGeral(main, comunicados)
  }
}

// Theme: follows the OS until the viewer picks one; the choice wins both ways.
const salvo = localStorage.getItem('regteia-tema')
if (salvo === 'light' || salvo === 'dark') document.documentElement.dataset.theme = salvo
document.getElementById('tema')!.addEventListener('click', () => {
  const atual =
    document.documentElement.dataset.theme ?? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  const novo = atual === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = novo
  localStorage.setItem('regteia-tema', novo)
  window.dispatchEvent(new Event('regteia:tema'))
})
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => window.dispatchEvent(new Event('regteia:tema')))

window.addEventListener('regteia:comunicados', (e) => {
  comunicados = (e as CustomEvent<boolean>).detail
  void rota()
})
window.addEventListener('hashchange', () => void rota())
void rota()
