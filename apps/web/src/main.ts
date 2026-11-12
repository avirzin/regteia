import './style.css'
import { iniciarIdioma, t } from './i18n'
import { paginaVisaoGeral } from './overview'
import { paginaEstatisticas } from './stats'

const main = document.getElementById('app')!
let desmontar: (() => void) | undefined
let comunicados = false
let pagina: 'estatisticas' | 'visao-geral' = 'visao-geral'

async function rota(): Promise<void> {
  desmontar?.()
  desmontar = undefined
  pagina = location.hash.startsWith('#/estatisticas') ? 'estatisticas' : 'visao-geral'
  document.querySelectorAll<HTMLAnchorElement>('nav a').forEach((a) => {
    if (a.dataset.rota === pagina) a.setAttribute('aria-current', 'page')
    else a.removeAttribute('aria-current')
  })
  if (pagina === 'estatisticas') {
    document.title = `${t('app.nav.estatisticas')} · Regteia`
    await paginaEstatisticas(main)
  } else {
    document.title = `${t('app.nav.visaoGeral')} · Regteia`
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

// Language: the overview re-translates itself in place (keeps the layout); the dashboard is cheap to redraw.
iniciarIdioma()
window.addEventListener('regteia:idioma', () => {
  document.title = `${t(pagina === 'estatisticas' ? 'app.nav.estatisticas' : 'app.nav.visaoGeral')} · Regteia`
  if (pagina === 'estatisticas') void rota()
})

window.addEventListener('regteia:comunicados', (e) => {
  comunicados = (e as CustomEvent<boolean>).detail
  void rota()
})
window.addEventListener('hashchange', () => void rota())
void rota()
