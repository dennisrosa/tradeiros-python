import os
import sys
from dotenv import load_dotenv

# Garantir que o diretório 'src' local tenha prioridade nas importações
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

# Carrega as variáveis de ambiente do .env local antes de configurar a classe Tradeiros
load_dotenv()

from dash import Dash, html, dcc, Input, Output, State, callback, no_update
from datetime import datetime
import dash_ag_grid as dag
import pandas as pd
import io
import base64
import matplotlib
matplotlib.use('Agg') # Evita problemas com threads e UI em ambiente server
from tradeiros.Tradeiros import Tradeiros

# 1. Configurações Globais / Cores e Estilos de Identidade Visual HP
COLORS = {
    'background': '#0b0c10',       # Fundo da página
    'container': '#1f2833',        # Fundo dos cards
    'text': '#c5c6c7',             # Texto Principal
    'accent': '#f4b41a',           # Dourado HP (Novo)
    'accent_dark': '#bd8d12',      # Dourado Escuro
}
t = Tradeiros("okx")

# Definição fixa das colunas para evitar NameError
GRID_COLUMNS = ['tipo', 'operacao', 'min', 'max', 'qtd', 'valor', 'reduce', '%']

def fig_to_uri(fig):
    """Converte uma figura do Matplotlib para uma URI de imagem base64"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', transparent=True)
    buf.seek(0)
    img_str = f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"
    return img_str

def get_processed_data():
    """Função auxiliar para capturar e formatar dados e patrimônio"""
    df = t.atualizar()
    patrimonio = t.patrimonio() 
    
    # Gera os gráficos
    fig = t.graficos()
    # Personalização para o tema escuro do dashboard
    fig.patch.set_facecolor(COLORS['container']) 
    for ax in fig.axes:
        ax.set_facecolor(COLORS['container'])
        ax.title.set_color(COLORS['accent'])
        # Distingue entre labels externos e internos (autopct) 
        for text in ax.texts:
            if '%' in text.get_text():
                text.set_color('#1f2833') # Cor escura para contraste nas fatias claras
                text.set_weight('bold')
                text.set_fontsize(10)
            else:
                text.set_color(COLORS['text']) # Cor clara para labels externos
        
    chart_uri = fig_to_uri(fig)
    
    df['%'] = df['%'].round(2) 
    df['qtd_sum'] = df['qtd_sum'].astype(int) 
    df = df[['tipo', 'operacao', 'preco_min', 'preco_max', 'qtd_ordens', 'qtd_sum', 'reduce', '%']]
    df = df.rename(columns={'preco_min':'min', 'preco_max':'max', 'qtd_ordens':'qtd', 'qtd_sum':'valor'})
    return df.to_dict("records"), patrimonio, chart_uri

# Cores movidas para o topo

app = Dash(
    __name__, 
    external_stylesheets=[
        "https://unpkg.com/ag-grid-community/dist/styles/ag-grid.css",
        "https://unpkg.com/ag-grid-community/dist/styles/ag-theme-alpine-dark.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" # FontAwesome para o olho
    ]
)

app.layout = html.Div([
    # CACHE DE DADOS
    dcc.Store(id='raw-data-store', data={'records': [], 'patrimonio': 0, 'chart_uri': ''}),
    
    # ESTADO DE PRIVACIDADE (Inicia True para esconder)
    dcc.Store(id='privacy-store', data=True),
    
    # COMPONENTE DE INTERVALO (30 Segundos)
    dcc.Interval(id='update-interval', interval=30*1000, n_intervals=0),

    # BOTÃO DE PRIVACIDADE NO TOPO DIREITO
    html.Div([
        html.Button(
            html.I(id='privacy-icon', className="fas fa-eye-slash", style={'color': COLORS['accent'], 'fontSize': '28px'}),
            id='privacy-button',
            n_clicks=0,
            style={
                'backgroundColor': 'transparent',
                'border': 'none',
                'cursor': 'pointer',
                'padding': '15px'
            }
        )
    ], style={'position': 'absolute', 'top': '10px', 'right': '20px', 'zIndex': '1000'}),

    # TOPPER / LOGO SECTION
    html.Div([
        html.Img(src="https://tradeiros.com.br/assets/logo_hp-BY7tjs3l.png", 
                 style={'height': '50px', 'marginBottom': '5px'}),
        
        # LABEL DE ÚLTIMA ATUALIZAÇÃO
        html.Div(id='last-update-label', 
                 children="Iniciando conexão...",
                 style={
                     'fontSize': '11px', 
                     'color': COLORS['text'], 
                     'opacity': '0.7',
                     'fontStyle': 'italic',
                     'marginTop': '-5px'
                 })
    ], style={'textAlign': 'center', 'padding': '10px 0', 'backgroundColor': COLORS['background']}),

    # CONTAINER PRINCIPAL (LADO A LADO)
    html.Div([
        
        # COLUNA 1: Estratégia Clássica
        html.Div([
            html.Div([
                html.Div([
                    html.Img(src="/assets/escudo.png", style={'height': '30px', 'marginRight': '10px'}),
                    html.H3([
                        "Carteira Clássica ",
                        html.Span(id='patrimonio-value', children="($ 0.00)", style={'fontSize': '16px', 'opacity': '0.8', 'marginLeft': '10px'})
                    ], style={'textAlign': 'center', 'color': COLORS['accent'], 'margin': '0', 'fontWeight': 'bold', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'padding': '10px 0'}),
                    dag.AgGrid(
                        id='grid-classica', 
                        rowData=[], 
                        columnDefs=[
                            {
                                "field": i, 
                                # Alinha à direita colunas numéricas/decimais
                                #"cellStyle": {"textAlign": "right"} if i in ["valor", "%"] else {}
                            } for i in GRID_COLUMNS
                        ],
                        defaultColDef={
                            "resizable": False, 
                            "sortable": False, 
                            "filter": False,
                            "flex": 1,
                        },
                        # Condicional para colorir as linhas: Verde (Buy) / Vermelho (Sell)
                        getRowStyle={
                            "styleConditions": [
                                {
                                    "condition": "params.data.tipo !== 'protected' && params.data.operacao === 'buy'",
                                    "style": {"color": "#22c55e"}
                                },
                                {
                                    "condition": "params.data.tipo !== 'protected' && params.data.operacao === 'sell'",
                                    "style": {"color": "#ef4444"}
                                },
                                {
                                    "condition": "params.data.tipo === 'protected'",
                                    "style": {"color":  COLORS['accent'], "fontWeight": "bold"}
                                },                                
                            ]
                        },
                        dashGridOptions={"pagination": False},
                        className="ag-theme-alpine-dark", 
                        style={"height": "500px", "width": "100%"}
                    ),
                    
                    # ÁREA DOS GRÁFICOS (MATPLOTLIB)
                    html.Div([
                        html.Img(id='chart-img', style={'width': '100%', 'borderRadius': '0 0 15px 15px', 'marginTop': '5px'})
                    ], style={'padding': '0 5px 5px 5px'})
            ], style={'backgroundColor': COLORS['container'], 'borderRadius': '15px', 'overflow': 'hidden', 'boxShadow': '0px 10px 30px rgba(0,0,0,0.5)'})
        ], style={'flex': '1', 'minWidth': '400px', 'padding': '5px'}), 
        
        # COLUNA 2: Estratégia Agressiva 
        html.Div([
            html.Div([
                html.Div([
                    html.Img(src="/assets/caveira.png", style={'height': '30px', 'marginRight': '10px'}),
                    html.H3("Carteira Agressiva", 
                            style={'textAlign': 'center', 'color': COLORS['accent'], 'margin': '0', 'fontWeight': 'bold', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'padding': '10px 0'}),
                
                html.Div([
                    html.Div([
                        html.I(className="fas fa-chart-line", style={'fontSize': '48px', 'color': COLORS['accent'], 'opacity': '0.3'}),
                        html.P("Conteúdo Agressivo em Breve", 
                               style={'marginTop': '20px', 'color': COLORS['text'], 'fontStyle': 'italic', 'opacity': '0.5'})
                    ], style={'textAlign': 'center'})
                ], style={
                    'height': '400px', 
                    'display': 'flex', 
                    'alignItems': 'center', 
                    'justifyContent': 'center',
                    'backgroundColor': COLORS['container'],
                    'border': f'2px dashed {COLORS["accent"]}',
                    'borderRadius': '0 0 15px 15px',
                    'margin': '-2px'
                })
            ], style={'backgroundColor': COLORS['container'], 'borderRadius': '15px', 'boxShadow': '0px 10px 30px rgba(0,0,0,0.5)'})
        ], style={'flex': '1', 'minWidth': '400px', 'padding': '5px'}) 
        
    ], style={'display': 'flex', 'flexDirection': 'row', 'flexWrap': 'nowrap', 'maxWidth': '100%', 'margin': '0 10px'})
], style={
    'backgroundColor': COLORS['background'], 
    'minHeight': '100vh', 
    'overflowX': 'hidden',
    'overflowY': 'auto', # Permite scroll se os gráficos forem grandes
    'fontFamily': '"Segoe UI", Roboto, Helvetica, Arial, sans-serif',
    'color': COLORS['text'],
    'paddingBottom': '20px'
})
    
# CSS Customizado
app.index_string = f'''
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>Tradeiros HP Dashboard</title>
        {{%favicon%}}
        {{%css%}}
        <style>
            body {{
                margin: 0;
            }}
            .ag-theme-alpine-dark {{
                --ag-background-color: {COLORS['container']};
                --ag-odd-row-background-color: rgba(255, 255, 255, 0.03);
                --ag-header-background-color: {COLORS['container']};
                --ag-border-color: #333;
                --ag-foreground-color: {COLORS['text']};
                --ag-row-height: 35px;
                --ag-header-height: 35px;
                --ag-font-size: 13px;
            }}
            .ag-row-even {{
                background-color: {COLORS['container']} !important;
                color: {COLORS['text']};
                border-bottom: 1px solid #333 !important;
            }}
            .ag-row-odd {{
                background-color: #1a222c !important; /* Cor levemente diferente para o efeito zebra */
                color: {COLORS['text']};
                border-bottom: 1px solid #333 !important;
            }}
            .ag-header-cell {{
                background-color: {COLORS['background']} !important;
                border-bottom: 2px solid {COLORS['accent']} !important;
            }}
        </style>
    </head>
    <body style="margin: 0;">
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
'''

# 1. CALLBACK DE BUSCA DE DADOS (API - A cada 30s)
@callback(
    Output('raw-data-store', 'data'),
    Output('last-update-label', 'children'),
    Output('last-update-label', 'style'),
    Input('update-interval', 'n_intervals')
)
def fetch_api_data(n):
    try:
        records, patrimonio, chart_uri = get_processed_data()
        current_time = datetime.now().strftime("%H:%M:%S")
        status_msg = f"Última atualização: {current_time}"
        status_style = {'fontSize': '12px', 'color': COLORS['text'], 'opacity': '0.7', 'fontStyle': 'italic', 'marginTop': '-5px'}
        return {'records': records, 'patrimonio': patrimonio, 'chart_uri': chart_uri}, status_msg, status_style
    except Exception as e:
        status_msg = "⚠️ erro na execução da api (re tentando...)"
        status_style = {'fontSize': '12px', 'color': '#ef4444', 'fontWeight': 'bold', 'marginTop': '-5px'}
        return no_update, status_msg, status_style

# 2. CALLBACK DE ALTERNAR PRIVACIDADE (BOTÃO)
@callback(
    Output('privacy-store', 'data'),
    Output('privacy-icon', 'className'),
    Input('privacy-button', 'n_clicks'),
    State('privacy-store', 'data')
)
def toggle_privacy(n, is_hidden):
    if n == 0: 
        return is_hidden, "fas fa-eye-slash" if is_hidden else "fas fa-eye"
    new_state = not is_hidden
    new_icon = "fas fa-eye-slash" if new_state else "fas fa-eye"
    return new_state, new_icon

# 3. CALLBACK DE EXIBIÇÃO (INSTANTÂNEO - SEM API)
@callback(
    Output('grid-classica', 'rowData'),
    Output('patrimonio-value', 'children'),
    Output('chart-img', 'src'),
    Input('raw-data-store', 'data'),
    Input('privacy-store', 'data')
)
def render_display(raw_data, is_hidden):
    if not raw_data or not raw_data['records']:
        return [], "($ ***)" if is_hidden else "($ 0.00)"
        
    records = [dict(r) for r in raw_data['records']] # Cópia para não alterar o cache
    patrimonio = raw_data['patrimonio']
    
    # Aplica máscara de privacidade
    patrimonio_str = "($ ***)" if is_hidden else f"($ {patrimonio:,.2f})"
    if is_hidden:
        for row in records:
            row['valor'] = "***"
            
    return records, patrimonio_str, raw_data.get('chart_uri', '')

if __name__ == '__main__':
    # Rodando externamente para que você possa abrir o link clássico no navegador
    app.run(jupyter_mode="external", host='127.0.0.1', port=8050, debug=True)