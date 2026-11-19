from tradeiros.ExchangeBase import ExchangeBase
from okx import Account, Trade, MarketData
import pandas as pd
import sys
import os
import json
from datetime import datetime

class Okx(ExchangeBase):
    def __init__(self, api_key=None, api_secret=None, passphrase=None, flag='0', sufixo=None):

        # Ajusta nome das chaves com base no sufixo caso fornecido
        suffix_str = sufixo if sufixo else ''

        # Tenta pegar dos parâmetros; se não passar, tenta pegar das variáveis de ambiente globais
        key = api_key or os.getenv(f'OKX_API_KEY{suffix_str}')
        secret = api_secret or os.getenv(f'OKX_API_SECRET{suffix_str}')
        pass_phrase = passphrase or os.getenv(f'OKX_PASSPHRASE{suffix_str}')
        flag_val = os.getenv('OKX_FLAG', flag)

        if not key or not secret or not pass_phrase:
            raise ValueError("As credenciais da OKX não foram fornecidas.")

        self.account = Account.AccountAPI(
            api_key=key,
            api_secret_key=secret,
            passphrase=pass_phrase,
            flag=flag_val,
            debug=False
        )

        self.trade = Trade.TradeAPI(
            api_key=key,
            api_secret_key=secret,
            passphrase=pass_phrase,
            flag=flag_val,
            debug=False    
        )

        self.market = MarketData.MarketAPI(
            api_key=key,
            api_secret_key=secret,
            passphrase=pass_phrase,
            flag=flag_val,
            debug=False   
        )

    def atualizar(self):
        df = self.get_ordens()
        patrimonio = self.get_patrimonio()
        df = self.consolidate(df, patrimonio, self.get_btc_preco(), posicoes=self.get_posicoes())
        return df, patrimonio


    def _get_btc_balance_detail(self):
        try:
            result = self.account.get_account_balance(ccy='BTC')
            if 'data' not in result:
                print(f"Erro OKX (Balance): {result}")
                return {}
            account_data = result.get('data', [])
            if account_data:
                for account_detail in account_data:
                    for balance_detail in account_detail.get('details', []):
                        if balance_detail.get('ccy') == 'BTC':
                            return balance_detail
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Balance): {e}")
        return {}

    def get_patrimonio(self):
        detail = self._get_btc_balance_detail()
        eq = detail.get('eq', 0)
        return float(eq) * self.get_btc_preco()

    def get_margem_disponivel(self):
        detail = self._get_btc_balance_detail()
        avail_bal = detail.get("availBal", 0)
        return float(avail_bal)

    def get_alavancagem(self):
        try:
            result = self.account.get_leverage(mgnMode="cross", instId="BTC-USD-SWAP")
            return float(result["data"][0]["lever"])
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha ao consultar alavancagem OKX: {e}")
            return 2.0

    def get_btc_preco(self):
        #Recuperar o preco atual do BTC
        try:
            ticker_result = self.market.get_ticker(instId='BTC-USD-SWAP')
            if not ticker_result.get('data'):
                print(f"Erro OKX (Ticker): {ticker_result}")
                return 1.0 # Fallback para evitar divisão por zero se usado
            return float(ticker_result["data"][0].get('last', 0))
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Ticker): {e}")
            return 1.0

    def get_ordens(self):
        df_limit = self.load_limit_orders_okx()
        df_market = self.load_market_orders_okx()
        df = pd.concat([df_limit, df_market]).sort_values('preco', ascending = True)
        return df

    def get_short_protecao(self):
        # Recuperar o SHORT Aberto (hedge mode: filtra posSide == 'short')
        try:
            posicao_btc = self.account.get_positions(instId='BTC-USD-SWAP')
            if not posicao_btc.get('data'):
                print(f"Erro OKX (Positions): {posicao_btc}")
                return 0
            for pos in posicao_btc['data']:
                if pos.get('posSide') == 'short':
                    return -abs(float(pos.get('pos', 0) or 0))
            # Fallback (net mode): sem posSide, usa a primeira posição
            return posicao_btc['data'][0].get('pos', 0)
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Positions): {e}")
            return 0

    def get_posicoes(self):
        """Retorna as posições abertas (long e short) como linhas 'protected'.

        Em hedge mode a OKX devolve uma posição por lado (posSide = long/short).
        O campo 'qtd' é assinado em contratos: long positivo, short negativo.
        """
        colunas = ['par', 'tipo', 'operacao', 'preco', 'qtd', 'reduce', 'data_criacao']
        try:
            result = self.account.get_positions(instId='BTC-USD-SWAP')
            rows = []
            for pos in result.get('data', []):
                qtd = float(pos.get('pos', 0) or 0)
                if qtd == 0:
                    continue
                pos_side = pos.get('posSide', 'net')
                # net mode: pos negativo => short
                if pos_side == 'short':
                    operacao, tipo = 'sell', 'short'
                elif pos_side == 'long':
                    operacao, tipo = 'buy', 'long'
                else:
                    if qtd < 0:
                        operacao, tipo = 'sell', 'short'
                    else:
                        operacao, tipo = 'buy', 'long'

                u_time = pos.get('uTime')
                data_criacao = pd.to_datetime(float(u_time), unit='ms').strftime('%d/%m %H:%M') if u_time else ''
                qtd_assinado = -abs(qtd) if operacao == 'sell' else abs(qtd)

                rows.append({
                    'par': 'BTC-USD-SWAP',
                    'tipo': tipo,
                    'operacao': operacao,
                    'preco': float(pos.get('avgPx', 0) or 0),
                    'qtd': qtd_assinado,
                    'reduce': 'false',
                    'data_criacao': data_criacao,
                })
            return pd.DataFrame(rows, columns=colunas)
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Posicoes): {e}")
            return pd.DataFrame(columns=colunas)

    def load_limit_orders_okx(self):
        try:
            orders = self.trade.get_order_list()
            if 'data' not in orders:
                print(f"Erro OKX (Limit Orders): {orders}")
                return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])
            df = pd.DataFrame(orders['data'])
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Limit Orders): {e}")
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])

        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])

        if 'posSide' not in df.columns:
            df['posSide'] = 'net'
        df = df[['instId', 'ordType', 'px', 'reduceOnly', 'side', 'sz', 'cTime', 'posSide']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'px':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0.0)
        df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0.0)
        # Converte timestamp para formato legível
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def load_market_orders_okx(self):
        try:
            result = self.trade.order_algos_list(ordType ='limit')
            if 'data' not in result:
                print(f"Erro OKX (Market/Algo Orders): {result}")
                return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])
            df = pd.DataFrame(result['data'])
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Market/Algo Orders): {e}")
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])

        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao', 'posSide'])

        if 'posSide' not in df.columns:
            df['posSide'] = 'net'
        df = df[['instId', 'ordType', 'slTriggerPx','reduceOnly', 'side', 'sz', 'cTime', 'posSide']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'slTriggerPx':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0.0)
        df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0.0)
        # Converte timestamp para formato legível
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def consolidate(self, df, allocation, btc_price, short_thp=None, posicoes=None):
        now_str = datetime.now().strftime('%d/%m %H:%M')

        colunas = ['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao']

        if df is not None and not df.empty:
            df_agrupado = df.copy()
            if 'posSide' not in df_agrupado.columns:
                df_agrupado['posSide'] = 'net'
            if 'reduce' not in df_agrupado.columns:
                df_agrupado['reduce'] = 'false'
            df_agrupado['reduce'] = df_agrupado['reduce'].astype(str)
            df_agrupado = df_agrupado.sort_values('preco', ascending=True).reset_index(drop=True)

            # Separa blocos de preço: dentro de cada combinação (tipo/operação/reduce/posSide),
            # abre um novo bloco quando o salto entre ordens consecutivas passar de 1% do preço médio.
            chaves = ['tipo', 'operacao', 'reduce', 'posSide']
            df_agrupado['bloco'] = 0
            for _, sub in df_agrupado.groupby(chaves, dropna=False):
                sub = sub.sort_values('preco')
                preco_medio = sub['preco'].abs().mean()
                limite = preco_medio * 0.01 if preco_medio > 0 else 0.0
                diffs = sub['preco'].diff().abs()
                clusters = (diffs > limite).cumsum()
                df_agrupado.loc[sub.index, 'bloco'] = clusters.values

            # Agrupa por valor + bloco para separar ordens normais/reduce, long/short e blocos de preço.
            agrupado = df_agrupado.groupby(
                ['tipo', 'operacao', 'reduce', 'posSide', 'bloco'], dropna=False
            ).agg(
                par=('par', 'first'),
                preco_min=('preco', 'min'),
                preco_max=('preco', 'max'),
                qtd_ordens=('preco', 'count'),
                qtd_sum=('qtd', 'sum'),
                data_criacao=('data_criacao', 'min'),
            ).reset_index()

            agrupado = agrupado[colunas]
        else:
            agrupado = pd.DataFrame(columns=colunas)

        # Posições abertas: uma linha por posição, tipo 'long' ou 'short'
        if posicoes is not None and not posicoes.empty:
            for _, p in posicoes.iterrows():
                tipo_pos = p.get('tipo')
                if tipo_pos not in ('long', 'short'):
                    tipo_pos = 'long' if p['operacao'] == 'buy' else 'short'
                agrupado.loc[len(agrupado)] = [
                    p['par'], tipo_pos, p['operacao'], p['preco'], p['preco'],
                    0, float(p['qtd']), p.get('reduce', 'false'), p['data_criacao']
                ]
        elif short_thp is not None:
            # Compatibilidade: apenas short informado (net mode)
            agrupado.loc[len(agrupado)] = ['BTC-USD-SWAP', 'short', 'sell', btc_price, btc_price, 0, float(short_thp), 'false', now_str]

        # Ordenar por preco_max decrescente
        agrupado = agrupado.sort_values('preco_max', ascending=False).reset_index(drop=True)
        agrupado['tipo'] = agrupado['tipo'].str.replace('conditional', 'market')

        agrupado['qtd_sum'] = agrupado['qtd_sum'] * 100
        if allocation > 0:
            agrupado['%'] = (agrupado['qtd_sum'] * 100 / allocation).round(2)
        else:
            agrupado['%'] = 0.0
        return agrupado
