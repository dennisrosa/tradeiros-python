from tradeiros.okx.okx import Okx
from tradeiros.bybit.bybit import Bybit
from tradeiros.bitget.bitget import Bitget
import os
from dotenv import load_dotenv, find_dotenv

class Tradeiros:
    def __init__(self, exchange, descricao=None, sufixo=None, **kwargs):
        load_dotenv(find_dotenv()) 
        
        self.exchange_name = exchange
        self.descricao = descricao
        self.sufixo = sufixo
        
        # Repassa o sufixo explicitamente para a exchange para formatação de variáveis de ambiente
        kwargs['sufixo'] = sufixo

        if exchange == "okx":
            self.exchange = Okx(**kwargs)
        elif exchange == "bybit":
            self.exchange = Bybit(**kwargs)
        elif exchange == "bitget":
            self.exchange = Bitget(**kwargs)
        else:
            raise ValueError("Exchange não suportada")

    def gerar_dataset_grafico(self):
        import pandas as pd
        
        # Usa os dados da instância salvos após o atualizar()
        df = self._df
        
        try:
            protected_row = df[df['tipo'] == 'protected']
            if not protected_row.empty:
                protegido = float(abs(protected_row['qtd_sum'].iloc[0]))
            else:
                protegido = 0.0
        except (IndexError, KeyError):
            protegido = 0.0

        valores = [protegido, self.patrimonio() - protegido]
        rotulos = ['Protegido', 'Exposto']

        df_exposicao = pd.DataFrame({
            'Categoria': rotulos,
            'Valor': valores,
            'Percentual': [f"{(v/sum(valores)*100):.1f}" if sum(valores) > 0 else "0.0" for v in valores]
        })

        df_exposicao['Cor'] = ['#ff9999', '#66b3ff']  
        df_exposicao['Explode'] = [0.05, 0]  

        # Filtra tipos e agrupa
        df_margem = df.groupby('tipo').agg(
            Valor=('qtd_sum', 'sum')
        ).abs().reset_index()

        # Adiciona linha de margem remanescente
        patrimonio_total_alocacao = self.patrimonio() * 2 # Exemplo baseado na lógica anterior
        margem_restante = patrimonio_total_alocacao - df_margem['Valor'].sum()
        
        df_margem.loc[len(df_margem)] = ['margem', max(0, margem_restante)]
        df_margem['Percentual'] = (df_margem['Valor'] * 100 / df_margem['Valor'].sum()).round(1)
        
        # Ajusta cores baseado no número de categorias encontradas
        cores_base = ['#ff9999', '#66b3ff', '#ffcc99', '#99ff99', '#c2c2f0', '#ffb3e6']
        df_margem['Cor'] = [cores_base[i % len(cores_base)] for i in range(len(df_margem))]
        df_margem['Explode'] = [0.02] * len(df_margem)
        
        df_margem = df_margem.rename(columns={'tipo': 'Categoria'})
        df_margem['Categoria'] = df_margem['Categoria'].replace({
            'limit': 'Limite',
            'market': 'Mercado', 
            'protected': 'Protegido',
            'margem': 'Margem'
        })

        return df_exposicao, df_margem

    def graficos(self):
        df_exposicao, df_margem = self.gerar_dataset_grafico()
        import matplotlib.pyplot as plt
        import numpy as np

        # Reduzi o tamanho da figura de (14, 6) para (10, 4)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

        # ===== GRÁFICO 1: Exposição =====
        ax1.pie(df_exposicao['Valor'], 
                labels=df_exposicao['Categoria'],
                colors=df_exposicao['Cor'],
                autopct='%1.1f%%',
                startangle=90,
                explode=df_exposicao['Explode'],
                shadow=True,
                textprops={'fontsize': 10}) # Fonte reduzida

        ax1.set_title('Exposição', fontsize=12, fontweight='bold')
        ax1.axis('equal')

        # ===== GRÁFICO 2: Margem =====
        ax2.pie(df_margem['Valor'],
                labels=df_margem['Categoria'],
                colors=df_margem['Cor'],
                autopct='%1.1f%%',
                startangle=90,
                explode=df_margem['Explode'],
                shadow=True,
                textprops={'fontsize': 10}) # Fonte reduzida


        ax2.set_title('Margem', fontsize=12, fontweight='bold')
        ax2.axis('equal')

        plt.tight_layout()
        
        # Fecha a figura no estado global para evitar renderização dupla no Jupyter
        plt.close(fig)
        
        return fig


    def atualizar(self):
        df, patrimonio = self.exchange.atualizar()
        self._df = df
        self._patrimonio = patrimonio
        return self._df

    def patrimonio(self):
        return self._patrimonio
        
if __name__ == "__main__":
    tradeiros = Tradeiros("okx")
    df = tradeiros.atualizar()
    print(df)
    print("Patrimônio: ", tradeiros.patrimonio())
    print("1% do patrimônio: ", tradeiros.patrimonio()*0.01)

    print("\n")
    
    #tradeiros = Tradeiros("bitget")
    #df, patrimonio = tradeiros.atualizar()
    #print(df)
    #print("Patrimônio: ", patrimonio)
    #print("1% do patrimônio: ", patrimonio*0.01)

        