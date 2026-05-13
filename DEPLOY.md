# Guia de Deploy — Portal CVM

O portal já está containerizado com Docker e pronto para ser publicado.  
Escolha uma das plataformas abaixo e siga o passo-a-passo.

---

## Opção 1 — Railway (Recomendado para iniciantes)

**Por que Railway?**
- Sem sleep automático (link sempre disponível)
- $5 de crédito grátis por mês (suficiente para uso leve)
- Conecta direto ao GitHub — a cada `git push`, o site atualiza sozinho
- URL permanente: `https://portal-cvm.up.railway.app`

**Pré-requisitos:** conta gratuita em [railway.app](https://railway.app)

**Passo a passo:**
1. Acesse [railway.app](https://railway.app) → clique em **New Project**
2. Escolha **Deploy from GitHub repo**
3. Autorize o GitHub e selecione o repositório `portal-cvm`
4. Railway detecta o `Dockerfile` automaticamente e inicia o build
5. Após o deploy, clique em **Settings → Domains → Generate Domain**
6. Sua URL pública estará pronta

**Variáveis de ambiente (opcional):**
Em **Settings → Variables**, adicione se quiser customizar:
```
CVM_MAX_YEAR=2024
CVM_CACHE_TTL_HOURS=24
```

---

## Opção 2 — Render

**Por que Render?**
- Muito popular, fácil de usar
- Tier gratuito disponível (mas **dorme após 15 min sem acesso** — primeira visita demora ~30s para acordar)
- Plano pago ($7/mês) é sempre ativo
- URL permanente: `https://portal-cvm.onrender.com`

**Pré-requisitos:** conta gratuita em [render.com](https://render.com)

**Passo a passo:**
1. Acesse [render.com](https://render.com) → **New → Web Service**
2. Conecte o GitHub e selecione `portal-cvm`
3. Configure:
   - **Runtime:** Docker
   - **Branch:** main
   - **Health Check Path:** `/`
4. Clique em **Create Web Service**
5. Aguarde o build (~3–5 min) e sua URL estará disponível

**Variáveis de ambiente:**
Em **Environment**, adicione se necessário:
```
CVM_MAX_YEAR=2024
```

---

## Opção 3 — Fly.io (Melhor latência no Brasil)

**Por que Fly.io?**
- Servidor em São Paulo (região `gru`) = menor latência para usuários brasileiros
- Tier gratuito generoso (3 VMs compartilhadas)
- Mais técnico que os anteriores
- URL permanente: `https://portal-cvm.fly.dev`

**Pré-requisitos:** conta em [fly.io](https://fly.io) + instalar a CLI `flyctl`

**Instalar flyctl:**
```bash
# Windows (PowerShell)
iwr https://fly.io/install.ps1 -useb | iex
```

**Passo a passo:**
1. Faça login: `flyctl auth login`
2. Dentro da pasta `cvm-portal`, execute:
   ```bash
   flyctl launch --name portal-cvm --region gru --dockerfile Dockerfile
   ```
3. Confirme as configurações quando perguntado
4. Para fazer deploy: `flyctl deploy`
5. Para abrir no browser: `flyctl open`

**Re-deploy após mudanças:**
```bash
git push origin main  # não faz deploy automático no Fly.io
flyctl deploy         # precisa rodar manualmente
```

---

## Resumo comparativo

| | Railway | Render (grátis) | Render (pago) | Fly.io |
|---|---|---|---|---|
| Preço | ~$5/mês grátis | Grátis | $7/mês | Grátis |
| Sleep automático | Não | Sim (15 min) | Não | Não |
| Auto-deploy no push | Sim | Sim | Sim | Não |
| Latência no Brasil | Média | Média | Média | Baixa (SP) |
| Dificuldade | Fácil | Fácil | Fácil | Média |

---

## Cold Start (re-download de dados)

Independente da plataforma, após cada restart do servidor os dados da CVM são re-baixados (~30–60 segundos na primeira consulta). Isso é esperado — o cache não persiste entre restarts na configuração atual.

Para evitar isso no futuro, é possível configurar um **disco persistente** na plataforma escolhida.
