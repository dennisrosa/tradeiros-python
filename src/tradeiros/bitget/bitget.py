import os
import pandas as pd
import ccxt
from tradeiros.ExchangeBase import ExchangeBase

class Bitget(ExchangeBase):
    def __init__(self, api_key=None, api_secret=None, passphrase=None, flag='1', sufixo=None):

        suffix_str = sufixo if sufixo else ''

        key = api_key or os.getenv(f'BITGET_API_KEY{suffix_str}')
        secret = api_secret or os.getenv(f'BITGET_API_SECRET{suffix_str}')
        pass_phrase = passphrase or os.getenv(f'BITGET_PASSPHRASE{suffix_str}')

        if not key or not secret or not pass_phrase:
            raise ValueError("As credenciais da Bitget não foram fornecidas.")

        self.instance = ccxt.bitget({
            'apiKey': key,
            'secret': secret,
            'password': pass_phrase,
            'options': {
                'defaultType': 'swap',
            }
        })

    def get_patrimonio(self):
        """
        Calcula o patrimônio total em USD considerando apenas:
        - Coin-Margined (Inverso) - Onde BTC é usado como colateral
        """
        try:
            # Busca saldo especificamente da conta Coin-M
            balance = self.instance.fetch_balance({'productType': 'COIN-FUTURES'})
            total_btc = balance.get('BTC', {}).get('total', 0.0)
            
            return float(total_btc) * self.get_btc_preco()
        except Exception as e:
            print(f"Erro ao buscar patrimônio Bitget (Coin-M): {e}")
            return 0.0

    def get_btc_preco(self):
        """Recupera o preço atual do Bitcoin (Inverso)"""
        symbol = 'BTC/USD:BTC'
        try:
            ticker = self.instance.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            raise ValueError(f"Erro ao recuperar preço da Bitget: {e}")

    def get_ordens(self):
        """Busca todas as ordens abertas (Limite e Plano) para o par BTC Inverso"""
        symbol = 'BTC/USD:BTC'
        try:
            # 1. Busca ordens Limit padrão
            orders = self.instance.fetch_open_orders(symbol)
            
            # 2. Busca ordens de Plano (Trigger/Stop/Market Trigger)
            try:
                plan_orders = self.instance.fetch_open_orders(symbol, params={'planType': 'normal_plan'})
                orders.extend(plan_orders)
            except:
                pass

            if not orders:
                return pd.DataFrame(columns=['par', 'tipo', 'operacao', 'preco', 'reduce', 'qtd'])
            
            data = []
            for o in orders:
                preco_ordem = float(o.get('price') or o.get('stopPrice') or 0)
                amount = float(o.get('amount', 0))
                
                # Valor nocional em USD (Notional) = amount * preco
                usd_value = amount * (preco_ordem or self.get_btc_preco())
                
                # Formata a data de criação
                ts = o.get('timestamp')
                dt_str = pd.to_datetime(ts, unit='ms').strftime('%d/%m %H:%M') if ts else ''
                
                data.append({
                    'par': o['symbol'],
                    'tipo': o.get('type', 'limit'),
                    'operacao': o['side'],
                    'preco': preco_ordem,
                    'reduce': str(o.get('reduceOnly', 'false')).lower(),
                    'qtd': usd_value,
                    'data_criacao': dt_str
                })
            
            df = pd.DataFrame(data).sort_values('preco', ascending=True)
            return df
        except Exception as e:
            print(f"Erro ao buscar ordens Bitget: {e}")
            return pd.DataFrame(columns=['par', 'tipo', 'operacao', 'preco', 'reduce', 'qtd'])

    def get_short_protecao(self):
        """
        Retorna o valor total da posição aberta no par Inverso (BTC/USD:BTC).
        Shorts retornam valores negativos.
        """
        symbol = 'BTC/USD:BTC'
        try:
            price = self.get_btc_preco()
            # Busca apenas posições Coin-Margined (BTC como margem)
            positions = self.instance.fetch_positions(params={'productType': 'COIN-FUTURES', 'marginCoin': 'BTC'})
            
            for pos in positions:
                if pos['symbol'] == symbol:
                    contracts = float(pos.get('contracts', 0) or 0)
                    if contracts > 0:
                        # Valor nocional USD = Qtd em BTC * Preço
                        val_usd = contracts * price
                        if pos.get('side') == 'short':
                            return -abs(val_usd)
                        return abs(val_usd)
            return 0.0
        except Exception as e:
            print(f"Erro ao buscar posição short Bitget: {e}")
            return 0.0

    def consolidate(self, df, allocation, btc_price, short_thp):
        """Consolida as ordens e posições para exibição no relatório"""
        import datetime
        now_str = datetime.datetime.now().strftime('%d/%m %H:%M')
        
        if df.empty:
            agrupado = pd.DataFrame(columns=['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao'])
            agrupado.loc[0] = ['BTC/USD:BTC', 'protected', 'sell', btc_price, btc_price, 0, float(short_thp), 'false', now_str]
        else:
            df_agrupado = df.copy()
            # Identificador de grupos sequenciais
            df_agrupado['grupo_sequencial'] = ( 
                (df_agrupado['tipo'] != df_agrupado['tipo'].shift()) | 
                (df_agrupado['operacao'] != df_agrupado['operacao'].shift())
            ).cumsum()
            
            agrupado = df_agrupado.groupby('grupo_sequencial').agg({
                'par': 'first',
                'tipo': 'first',
                'operacao': 'first',
                'preco': ['min', 'max', 'count'],
                'qtd': 'sum',
                'reduce': 'first',
                'data_criacao': 'min'
            }).reset_index(drop=True)
            
            agrupado.columns = ['par', 'tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', 'data_criacao']
            # Adiciona linha de proteção (Short aberto)
            agrupado.loc[len(agrupado)] = ['BTC/USD:BTC', 'protected', 'sell', btc_price, btc_price , 0, float(short_thp), 'false', now_str]
        
        # Ordenar por preco_max decrescente
        agrupado = agrupado.sort_values('preco_max', ascending=False).reset_index(drop=True)
        agrupado['tipo'] = agrupado['tipo'].str.replace('conditional', 'market')

        # Cálculo da porcentagem de exposição sobre o patrimônio total
        if allocation > 0:
            agrupado['%'] = ((agrupado['qtd_sum'].abs() * 100) / allocation).round(2)
        else:
            agrupado['%'] = 0.0
            
        return agrupado

    def atualizar(self):
        """Ponto de entrada principal para a atualização dos dados da Bitget"""
        price = self.get_btc_preco()
        patrimonio = self.get_patrimonio()
        df_ordens = self.get_ordens()
        short = self.get_short_protecao()
        
        df_consolidado = self.consolidate(df_ordens, patrimonio, price, short)
        return df_consolidado, patrimonio