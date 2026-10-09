# Política de Segurança

## Como reportar uma vulnerabilidade

- **GitHub**: abrir uma *issue privada* de segurança em
  [github.com/frederico-kluser/mujoco-lab](https://github.com/frederico-kluser/mujoco-lab)
  (Security → Report a vulnerability).
- **Email**: o endereço do autor em `git log` / `git config user.email`
  (kluserhuu@gmail.com), com o assunto `[SECURITY] mujoco-lab`.

Não abra issues públicas para vulnerabilidades exploráveis.

## O que não fazer

- **Nunca divulgar segredos** — nem em issues, PRs, commits, logs ou screenshots
  (chaves de API, tokens, passwords, credenciais de serviços).
- Não explorar a falha para além do necessário à prova de conceito, e nunca contra
  sistemas de terceiros.
- Não incluir dados pessoais em relatórios.

## Política de resposta

- Reconhecimento do relatório em **até 5 dias úteis**.
- Avaliação e plano de correção em **até 30 dias**; correções publicadas com aviso
  (CVE via GitHub Security Advisories quando aplicável).
- Divulgação coordenada: o relator pode publicar os detalhes depois da correção.

Este projeto é mantido por um único autor, num tempo voluntário — obrigado por ajudar
a mantê-lo seguro.
