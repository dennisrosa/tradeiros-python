# Plano: Recuperar Margem Disponível - OKX Coin-M Inverse Cross 2x

## Resumo Executivo

Para recuperar a **margem disponível** em uma conta OKX operando em modo **inverse (Coin-M)**, **cross margin**, **2x alavancagem** em **BTC**, a API fornece:

- **`availBal`** no endpoint `GET /api/v5/account/balance` - saldo disponível em BTC (margem livre)

---

## API Primária: `GET /api/v5/account/balance`

**SDK call:** `self.account.get_account_balance(ccy='BTC')`

No modo **Futures** (single-currency margin) com posições cross abertas, o `details[]` para BTC retorna:

| Campo | Tipo | Descrição | Uso |
|-------|------|-----------|-----|
| `availBal` | String | **Margem disponível em BTC** | Principal - margem livre para novas posições |
| `eq` | String | Equity total em BTC (= cashBal + upl) | Patrimônio total |
| `cashBal` | String | Saldo de caixa em BTC | Saldo sem PnL não realizado |
| `frozenBal` | String | Saldo congelado (margem + ordens pendentes) | Margem em uso |
| `ordFrozen` | String | Margem congelada por ordens pendentes | Margem bloqueada por ordens |
| `upl` | String | PnL não realizado em BTC | Lucro/perda aberto |
| `mgnRatio` | String | **Margin ratio cross** (chave de risco) | <1.0 = risco liquidação |
| `imr` | String | Margem inicial requerida (BTC) | Margem inicial total |
| `mmr` | String | Margem de manutenção requerida (BTC) | Mínimo para não liquidar |
| `notionalLever` | String | Alavancagem efetiva | Verificar se está em 2x |

**Cálculos derivados:**

```
margem_disponivel = availBal (direto da API)
margem_em_uso = frozenBal - ordFrozen (margem nas posições abertas)
margem_total = eq (equity total)
margem_livre_pct = availBal / eq * 100 (% livre)
```

---

## Fórmulas Inverse (Coin-M)

Para `BTC-USD-SWAP` (contrato inverse, ctVal = 100 USD):

- **PnL não realizado**: `upl = (1/avgPx - 1/markPx) * pos * ctVal` (em BTC)
- **Notional USD**: `notionalUsd = sz * ctVal` (face value, NÃO multiplica por markPx)
- **Margem ratio**: `mgnRatio = adjEq / mmr` (< 1.0 = zona de liquidação)

---

## Passos de Implementação

| # | Ação | Arquivo | Detalhes |
|---|------|---------|----------|
| 1 | `get_margem_disponivel()` | `src/tradeiros/okx/okx.py` | Chamar `get_account_balance(ccy='BTC')`, extrair `availBal`, retornar `float` |
| 2 | Método abstrato | `src/tradeiros/ExchangeBase.py` | Adicionar `get_margem_disponivel()` abstrato |
| 3 | Implementar Bitget | `src/tradeiros/bitget/bitget.py` | `fetch_balance({'productType': 'COIN-FUTURES'})`, campo `free.BTC`, retornar `float` |
| 4 | Fachada Tradeiros | `src/tradeiros/Tradeiros.py` | Delegar `get_margem_disponivel()` |
| 5 | Dashboard | `dash/dashboard.py` | Ajustar gráfico existente na parte de margem para usar `get_margem_disponivel()` ao invés da lógica atual |
| 6 | Testes | `tests/test_okx.py` | Mock de `get_margem_disponivel()` |

---

## Observações

- O campo `availBal` já é retornado pelo endpoint que o projeto já chama (`get_account_balance`), mas atualmente é **descartado** no método `get_patrimonio()`.
- Para contas Futures mode com cross margin, os campos `mgnRatio`, `imr`, `mmr` só aparecem no `details[]` quando há posições cross abertas.
- O endpoint `risk-state` (GET /api/v5/account/risk-state) **NÃO se aplica** ao modo Futures - é exclusivo de Portfolio margin. Use `mgnRatio` do balance.
- O `BTC-USD-SWAP` no OKX é o perpetual inverse/coin-margined (ctVal=100 USD, margem e settlement em BTC).
