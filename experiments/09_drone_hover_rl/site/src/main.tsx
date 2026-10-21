import { StrictMode, Suspense, lazy } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { MotionUIThemeProvider } from "@/components/motion-ui/ui-theme"
// Armadilha conhecida: o alias "@/motion.theme" NÃO resolve — o ficheiro está na raiz do projeto,
// logo o import é relativo (um só provider, montado UMA vez na raiz).
import motionTheme from "../motion.theme"

// `/pecas` — a página das PEÇAS 3D e da montagem (pedido do dono, 2026-10-20). Carrega à parte (o three.js fica
// fora do bundle do cockpit) e o `sim_site.py` serve o mesmo `index.html` para qualquer rota sem ponto.
const PaginaPecas = lazy(() => import("@/paginas/pecas/pagina-pecas"))
const rota = window.location.pathname.replace(/\/+$/, "")
const ePaginaPecas = rota === "/pecas" || rota.startsWith("/pecas/")

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionUIThemeProvider theme={motionTheme}>
      {/* Tema FIXO em escuro (2026-10-10): o painel de piloto não muda de cor a meio de um voo. O
          `storageKey` novo (`tema`) ignora os valores `theme` deixados pelo antigo atalho `d` (que
          alternava dark/light cada vez que se voava à direita — defeito reportado pelo dono). */}
      <ThemeProvider defaultTheme="dark" storageKey="tema">
        {ePaginaPecas ? (
          <Suspense fallback={<div className="h-svh bg-[#0c1016]" />}>
            <PaginaPecas />
          </Suspense>
        ) : (
          <App />
        )}
      </ThemeProvider>
    </MotionUIThemeProvider>
  </StrictMode>
)
