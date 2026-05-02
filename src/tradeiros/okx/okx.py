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

        # Tenta pegar dos parÃƒÂ¢metros; se nÃƒÂ£o passar, tenta pegar das variÃƒÂ¡veis de ambiente globais
        key = api_key or os.getenv(f'OKX_API_KEY{suffix_str}')
        secret = api_secret or os.getenv(f'OKX_API_SECRET{suffix_str}')
        pass_phrase = passphrase or os.getenv(f'OKX_PASSPHRASE{suffix_str}')
        flag_val = os.getenv('OKX_FLAG', flag)

        if not key or not secret or not pass_phrase:
            raise ValueError("As credenciais da OKX nÃƒÂ£o foram fornecidas.")

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
        df = self.consolidate(df, patrimonio, self.get_btc_preco(), self.get_short_protecao())
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
            print(f"[{__import__("datetime").datetime.now().strftime("%d/%m %H:%M:%S")}] Falha ao consultar alavancagem OKX: {e}")
            return 2.0

    def get_btc_preco(self):
        #Recuperar o preco atual do BTC
        try:
            ticker_result = self.market.get_ticker(instId='BTC-USD-SWAP')
            if not ticker_result.get('data'):
                print(f"Erro OKX (Ticker): {ticker_result}")
                return 1.0 # Fallback para evitar divisÃƒÂ£o por zero se usado
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
        # Recuperar o SHORT Aberto
        try:
            posicao_btc = self.account.get_positions(instId='BTC-USD-SWAP')
            if not posicao_btc.get('data'):
                print(f"Erro OKX (Positions): {posicao_btc}")
                return 0
            return posicao_btc['data'][0].get('pos', 0)
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Positions): {e}")
            return 0

    def load_limit_orders_okx(self):
        try:
            orders = self.trade.get_order_list()
            if 'data' not in orders:
                print(f"Erro OKX (Limit Orders): {orders}")
                return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
            df = pd.DataFrame(orders['data'])
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Limit Orders): {e}")
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])

        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
        
        df = df[['instId', 'ordType', 'px', 'reduceOnly', 'side', 'sz', 'cTime']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'px':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0.0)
        df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0.0)
        # Converte timestamp para formato legÃƒÂ­vel
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def load_market_orders_okx(self):
        try:
            result = self.trade.order_algos_list(ordType ='limit')
            if 'data' not in result:
                print(f"Erro OKX (Market/Algo Orders): {result}")
                return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
            df = pd.DataFrame(result['data'])
        except Exception as e:
            print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Falha na rede OKX (Market/Algo Orders): {e}")
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])

        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
            
        df = df[['instId', 'ordType', 'slTriggerPx','reduceOnly', 'side', 'sz', 'cTime']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'slTriggerPx':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = pd.to_numeric(df['preco'], errors='coerce').fillna(0.0)
        df['qtd'] = pd.to_numeric(df['qtd'], errors='coerce').fillna(0.0)
        # Converte timestamp para formato legÃƒÂ­vel
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def consolidate(self, df, allocation, btc_price, short_thp):
        now_str = datetime.now().strftime('%d/%m %H:%M')
        
        if df.empty:
            agrupado = pd.DataFrame(columns=['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao'])
            agrupado.loc[0] = ['BTC-USD-SWAP', 'protected', 'sell', btc_price, btc_price, 0, float(short_thp), 'false', now_str]
        else:
            df_agrupado = df.copy()
            
            # Criar identificador de grupos baseado em mudanÃƒÂ§as sequenciais de tipo E operacao
            df_agrupado['grupo_sequencial'] = ( 
                (df_agrupado['tipo'] != df_agrupado['tipo'].shift()) | 
                (df_agrupado['operacao'] != df_agrupado['operacao'].shift())
            ).cumsum()
            
            # Agrupar por 'grupo_sequencial' e calcular estatÃƒÂ­sticas
            agrupado = df_agrupado.groupby('grupo_sequencial').agg({
                'par': 'first',
                'tipo': 'first',
                'operacao': 'first',
                'preco': ['min', 'max', 'count'],
                'qtd': 'sum',
                'reduce': 'first',
                'data_criacao': 'min'  # Pega a data mais antiga do grupo
            }).reset_index(drop=True)
            
            # Renomear colunas
            agrupado.columns = ['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao']
            # Adiciona linha de proteÃƒÂ§ÃƒÂ£o com data atual
            agrupado.loc[len(agrupado)] = ['BTC-USD-SWAP', 'protected', 'sell', btc_price, btc_price , 0, float(short_thp), 'false', now_str]
        
        # Ordenar por preco_max decrescente
        agrupado = agrupado.sort_values('preco_max', ascending=False).reset_index(drop=True)
        agrupado['tipo'] = agrupado['tipo'].str.replace('conditional', 'market')

        agrupado['qtd_sum'] = agrupado['qtd_sum'] * 100
        if allocation > 0:
            agrupado['%'] = (agrupado['qtd_sum'] * 100 / allocation).round(2)
        else:
            agrupado['%'] = 0.0
        return agrupado