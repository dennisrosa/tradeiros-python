from tradeiros.ExchangeBase import ExchangeBase
from okx import Account, Trade, MarketData
import pandas as pd
import sys
import os
import json

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
        df = self.consolidate(df, patrimonio, self.get_btc_preco(), self.get_short_protecao())
        return df, patrimonio


    def get_patrimonio(self):
        result = self.account.get_account_balance()
        eq = 0   
        account_data = result.get('data', [])
        if account_data:
            for account_detail in account_data:
                encontrou_btc = False
                for balance_detail in account_detail.get('details', []):
                    ccy = balance_detail.get('ccy')
                    
                    # Filtra apenas para BTC
                    if ccy == 'BTC':
                        encontrou_btc = True
                        cash_bal = balance_detail.get('cashBal')
                        avail_bal = balance_detail.get('availBal')
                        eq = balance_detail.get('eq')
                        break  # Sai do loop após encontrar BTC
                
                if not encontrou_btc:
                    print("Nenhum saldo de BTC encontrado nesta conta.")
        else:
            print("Nenhum dado de conta encontrado.")

        return float(eq) * self.get_btc_preco()

    def get_btc_preco(self):
        #Recuperar o preco atual do BTC
        ticker_result = self.market.get_ticker(instId='BTC-USD-SWAP')
        return float(ticker_result["data"][0]['last'])

    def get_ordens(self):
        df_limit = self.load_limit_orders_okx()
        df_market = self.load_market_orders_okx()
        df = pd.concat([df_limit, df_market]).sort_values('preco', ascending = True)
        return df

    def get_short_protecao(self):
        # Recuperar o SHORT Aberto
        posicao_btc = self.account.get_positions(instId='BTC-USD-SWAP')
        return posicao_btc['data'][0]['pos']

    def load_limit_orders_okx(self):
        orders = self.trade.get_order_list()
        str_data = json.dumps(orders)
        js = json.loads(str_data)
        df = pd.DataFrame(js['data'])
        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
        
        df = df[['instId', 'ordType', 'px', 'reduceOnly', 'side', 'sz', 'cTime']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'px':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = df['preco'].astype("float")
        df['qtd'] = df['qtd'].astype("float")
        # Converte timestamp para formato legível
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def load_market_orders_okx(self):
        result = self.trade.order_algos_list(ordType ='limit')
        str_data = json.dumps(result)
        js = json.loads(str_data)
        df = pd.DataFrame(js['data'])
        if df.empty:
            return pd.DataFrame(columns=['par', 'tipo', 'preco', 'reduce', 'operacao', 'qtd', 'data_criacao'])
            
        df = df[['instId', 'ordType', 'slTriggerPx','reduceOnly', 'side', 'sz', 'cTime']]
        df = df.rename(columns={'instId':'par', 'ordType':'tipo', 'slTriggerPx':'preco', 'reduceOnly':'reduce', 'side': 'operacao', 'sz':'qtd'})
        df['preco'] = df['preco'].astype("float")
        df['qtd'] = df['qtd'].astype("float")
        # Converte timestamp para formato legível
        df['data_criacao'] = pd.to_datetime(df['cTime'].astype(float), unit='ms').dt.strftime('%d/%m %H:%M')
        return df.sort_values('preco', ascending=False)

    def consolidate(self, df, allocation, btc_price, short_thp):
        import datetime
        now_str = datetime.datetime.now().strftime('%d/%m %H:%M')
        
        if df.empty:
            agrupado = pd.DataFrame(columns=['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao'])
            agrupado.loc[0] = ['BTC-USD-SWAP', 'protected', 'sell', btc_price, btc_price, 0, float(short_thp), 'false', now_str]
        else:
            df_agrupado = df.copy()
            
            # Criar identificador de grupos baseado em mudanças sequenciais de tipo E operacao
            df_agrupado['grupo_sequencial'] = ( 
                (df_agrupado['tipo'] != df_agrupado['tipo'].shift()) | 
                (df_agrupado['operacao'] != df_agrupado['operacao'].shift())
            ).cumsum()
            
            # Agrupar por 'grupo_sequencial' e calcular estatísticas
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
            # Adiciona linha de proteção com data atual
            agrupado.loc[len(agrupado)] = ['BTC-USD-SWAP', 'protected', 'sell', btc_price, btc_price , 0, float(short_thp), 'false', now_str]
        
        # Ordenar por preco_max decrescente
        agrupado = agrupado.sort_values('preco_max', ascending=False).reset_index(drop=True)
        agrupado['tipo'] = agrupado['tipo'].str.replace('conditional', 'market')

        agrupado['qtd_sum'] = agrupado['qtd_sum'] * 100
        agrupado['%'] = agrupado['qtd_sum'] * 100 / allocation
        return agrupado