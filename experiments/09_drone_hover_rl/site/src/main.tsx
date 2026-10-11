import { StrictMode } from "react"
import { createRoot } from "react-dom/client"

import "./index.css"
import App from "./App.tsx"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { MotionUIThemeProvider } from "@/components/motion-ui/ui-theme"
// Armadilha conhecida: o alias "@/motion.theme" NÃO resolve — o ficheiro está na raiz do projeto,
// logo o import é relativo (um só provider, montado UMA vez na raiz).
import motionTheme from "../motion.theme"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MotionUIThemeProvider theme={motionTheme}>
      {/* Tema FIXO em escuro (2026-10-10): o painel de piloto não muda de cor a meio de um voo. O
          `storageKey` novo (`tema`) ignora os valores `theme` deixados pelo antigo atalho `d` (que
          alternava dark/light cada vez que se voava à direita — defeito reportado pelo dono). */}
      <ThemeProvider defaultTheme="dark" storageKey="tema">
        <App />
      </ThemeProvider>
    </MotionUIThemeProvider>
  </StrictMode>
)
