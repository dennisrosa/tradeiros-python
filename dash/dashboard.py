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
classica = Tradeiros("okx", descricao="Carteira Clássica", sufixo="")
agressiva = Tradeiros("okx", descricao="Carteira Agressiva", sufixo="_AGRESSIVA")

# Definição fixa das colunas para evitar NameError
GRID_COLUMNS = ['operacao', 'range', 'valor', 'data', '%']

def fig_to_uri(fig):
    """Converte uma figura do Matplotlib para uma URI de imagem base64"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches='tight', transparent=True)
    buf.seek(0)
    img_str = f"data:image/png;base64,{base64.b64encode(buf.read()).decode('utf-8')}"
    return img_str

def process_wallet(tradeiros_instance):
    """Captura, formata e gera graficos para uma instancia Tradeiros"""
    df = tradeiros_instance.atualizar()
    patrimonio = tradeiros_instance.patrimonio()

    # Gera os graficos
    fig = tradeiros_instance.graficos()
    # Personalizacao para o tema escuro do dashboard
    fig.patch.set_facecolor(COLORS['container'])
    for ax in fig.axes:
        ax.set_facecolor(COLORS['container'])
        ax.title.set_color(COLORS['accent'])
        for text in ax.texts:
            if '%' in text.get_text():
                text.set_color('#1f2833')
                text.set_weight('bold')
                text.set_fontsize(10)
            else:
                text.set_color(COLORS['text'])

    chart_uri = fig_to_uri(fig)

    def formatar_texto(row):
        operacao = str(row['operacao']).upper()
        tipo = str(row['tipo']).upper()
        qtd = row['qtd_ordens']
        reduce = str(row['reduce']).lower() == 'true' if isinstance(row['reduce'], str) else bool(row['reduce'])

        if qtd > 1:
            ret = f"{operacao} SCALE-{int(qtd)} {tipo}"
        elif qtd == 0:
            ret = "SHORT"
        elif qtd == 1:
            ret = f"{operacao} STOP {tipo}"
        else:
            return None

        if reduce and qtd > 0:
            return "R " + ret
        return ret

    def formatar_range(row):
        p_min = row['preco_min']
        p_max = row['preco_max']
        if p_min == p_max:
            return f"{p_min:.1f}"
        return f"{p_min:.1f} a {p_max:.1f}"

    df['%'] = df['%'].round(2)

    df['raw_operacao'] = df['operacao']
    df['raw_tipo'] = df['tipo']

    df['range'] = df.apply(formatar_range, axis=1)
    df['operacao'] = df.apply(formatar_texto, axis=1)

    df = df.rename(columns={'qtd_sum': 'valor', 'data_criacao': 'data'})

    df = df[['operacao', 'range', 'valor', 'data', '%', 'raw_operacao', 'raw_tipo']]
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
    # CACHE DE DADOS (duas carteiras)
    dcc.Store(id='raw-data-classica', data={'records': [], 'patrimonio': 0, 'chart_uri': ''}),
    dcc.Store(id='raw-data-agressiva', data={'records': [], 'patrimonio': 0, 'chart_uri': ''}),

    # ESTADO DE PRIVACIDADE (Inicia True para esconder)
    dcc.Store(id='privacy-store', data=True),

    # COMPONENTE DE INTERVALO (10 Segundos)
    dcc.Interval(id='update-interval', interval=10*1000, n_intervals=0),

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
                        f"{classica.descricao} ",
                        html.Span(id='patrimonio-classica', children="($ 0.00)", style={'fontSize': '16px', 'opacity': '0.8', 'marginLeft': '10px'})
                    ], style={'textAlign': 'center', 'color': COLORS['accent'], 'margin': '0', 'fontWeight': 'bold', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'padding': '10px 0'}),
                    dag.AgGrid(
                        id='grid-classica', 
                        rowData=[], 
                        columnDefs=[], # Será preenchido pelo clientside callback
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
                                    "condition": "params.data.raw_tipo !== 'protected' && params.data.raw_operacao === 'buy'",
                                    "style": {"color": "#22c55e"}
                                },
                                {
                                    "condition": "params.data.raw_tipo !== 'protected' && params.data.raw_operacao === 'sell'",
                                    "style": {"color": "#ef4444"}
                                },
                                {
                                    "condition": "params.data.raw_tipo === 'protected'",
                                    "style": {"color":  COLORS['accent'], "fontWeight": "bold"}
                                },                                
                            ]
                        },
                        dashGridOptions={"pagination": False, "domLayout": "autoHeight"},
                        className="ag-theme-alpine-dark", 
                        style={"height": "auto", "maxHeight": "500px", "width": "100%", "overflowY": "auto"}
                    ),
                    
                    # AREA DOS GRAFICOS (MATPLOTLIB)
                    html.Div([
                        html.Img(id='chart-classica', style={'width': '100%', 'borderRadius': '0 0 15px 15px', 'marginTop': '5px'})
                    ], style={'padding': '0 5px 5px 5px'})
            ], style={'backgroundColor': COLORS['container'], 'borderRadius': '15px', 'overflow': 'hidden', 'boxShadow': '0px 10px 30px rgba(0,0,0,0.5)'})
        ], style={'flex': '1', 'minWidth': '400px', 'padding': '5px'}), 
        
        # COLUNA 2: Estrategia Agressiva
        html.Div([
            html.Div([
                html.Div([
                    html.Img(src="/assets/caveira.png", style={'height': '30px', 'marginRight': '10px'}),
                    html.H3([
                        f"{agressiva.descricao} ",
                        html.Span(id='patrimonio-agressiva', children="($ 0.00)", style={'fontSize': '16px', 'opacity': '0.8', 'marginLeft': '10px'})
                    ], style={'textAlign': 'center', 'color': COLORS['accent'], 'margin': '0', 'fontWeight': 'bold', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center', 'padding': '10px 0'}),
                    dag.AgGrid(
                        id='grid-agressiva',
                        rowData=[],
                        columnDefs=[],
                        defaultColDef={
                            "resizable": False,
                            "sortable": False,
                            "filter": False,
                            "flex": 1,
                        },
                        getRowStyle={
                            "styleConditions": [
                                {
                                    "condition": "params.data.raw_tipo !== 'protected' && params.data.raw_operacao === 'buy'",
                                    "style": {"color": "#22c55e"}
                                },
                                {
                                    "condition": "params.data.raw_tipo !== 'protected' && params.data.raw_operacao === 'sell'",
                                    "style": {"color": "#ef4444"}
                                },
                                {
                                    "condition": "params.data.raw_tipo === 'protected'",
                                    "style": {"color":  COLORS['accent'], "fontWeight": "bold"}
                                },
                            ]
                        },
                        dashGridOptions={"pagination": False, "domLayout": "autoHeight"},
                        className="ag-theme-alpine-dark",
                        style={"height": "auto", "maxHeight": "500px", "width": "100%", "overflowY": "auto"}
                    ),
                    html.Div([
                        html.Img(id='chart-agressiva', style={'width': '100%', 'borderRadius': '0 0 15px 15px', 'marginTop': '5px'})
                    ], style={'padding': '0 5px 5px 5px'})
            ], style={'backgroundColor': COLORS['container'], 'borderRadius': '15px', 'overflow': 'hidden', 'boxShadow': '0px 10px 30px rgba(0,0,0,0.5)'})
        ], style={'flex': '1', 'minWidth': '400px', 'padding': '5px'}) 
        
    ], style={
        'display': 'flex', 
        'flexDirection': 'row', 
        'flexWrap': 'wrap', # Permite quebrar linha no mobile (um abaixo do outro)
        'justifyContent': 'center', 
        'maxWidth': '1300px', # Limita a largura para reduzir espaços vazios no grid
        'margin': '20px auto', # Centraliza e adiciona respiro no topo
        'padding': '0 10px'
    })
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
            /* Centralizar texto dos cabeçalhos */
            .center-header .ag-header-cell-label {{
                justify-content: center !important;
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

# 1. CALLBACK DE BUSCA DE DADOS (API - A cada 10s)
@callback(
    Output('raw-data-classica', 'data'),
    Output('raw-data-agressiva', 'data'),
    Output('last-update-label', 'children'),
    Output('last-update-label', 'style'),
    Input('update-interval', 'n_intervals')
)
def fetch_api_data(n):
    try:
        records_c, patrimonio_c, chart_uri_c = process_wallet(classica)
        records_a, patrimonio_a, chart_uri_a = process_wallet(agressiva)
        current_time = datetime.now().strftime("%H:%M:%S")
        status_msg = f"Ultima atualizacao: {current_time}"
        status_style = {'fontSize': '12px', 'color': COLORS['text'], 'opacity': '0.7', 'fontStyle': 'italic', 'marginTop': '-5px'}
        data_c = {'records': records_c, 'patrimonio': patrimonio_c, 'chart_uri': chart_uri_c}
        data_a = {'records': records_a, 'patrimonio': patrimonio_a, 'chart_uri': chart_uri_a}
        return data_c, data_a, status_msg, status_style
    except Exception as e:
        import traceback
        print(f"Erro no fetch: {e}")
        traceback.print_exc()
        status_msg = "erro na execucao da api (re tentando...)"
        status_style = {'fontSize': '12px', 'color': '#ef4444', 'fontWeight': 'bold', 'marginTop': '-5px'}
        return no_update, no_update, status_msg, status_style

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

# 3. CALLBACK DE EXIBICAO (INSTANTANEO - SEM API)
@callback(
    Output('grid-classica', 'rowData'),
    Output('patrimonio-classica', 'children'),
    Output('chart-classica', 'src'),
    Output('grid-agressiva', 'rowData'),
    Output('patrimonio-agressiva', 'children'),
    Output('chart-agressiva', 'src'),
    Input('raw-data-classica', 'data'),
    Input('raw-data-agressiva', 'data'),
    Input('privacy-store', 'data')
)
def render_display(raw_data_c, raw_data_a, is_hidden):
    def apply_privacy(raw_data):
        if not raw_data or not raw_data['records']:
            return [], "($ ***)" if is_hidden else "($ 0.00)", ''

        records = [dict(r) for r in raw_data['records']]
        patrimonio = raw_data['patrimonio']

        patrimonio_str = "($ ***)" if is_hidden else f"($ {patrimonio:,.2f})"
        if is_hidden:
            for row in records:
                row['valor'] = "***"

        return records, patrimonio_str, raw_data.get('chart_uri', '')

    r_c, p_c, ch_c = apply_privacy(raw_data_c)
    r_a, p_a, ch_a = apply_privacy(raw_data_a)
    return r_c, p_c, ch_c, r_a, p_a, ch_a

# 4. CALLBACK RESPONSIVO (CLIENTSIDE) - Ajusta colunas para ambos grids
app.clientside_callback(
    """
    function(n, is_hidden) {
        const width = window.innerWidth;
        const isMobile = width < 700;
        const columns = ['operacao', 'range', 'valor', 'data', '%'];

        const colDefs = columns.map(i => {
            const isData = i === 'data';
            return {
                "field": i,
                "headerName": isData ? "DATA" : i.toUpperCase(),
                "hide": isData && isMobile,
                "headerClass": (i === 'operacao' || i === 'range' || i === 'data') ? "center-header" : "",
                "cellStyle": {
                    "textAlign": (i === 'operacao' || i === 'range' || i === 'data') ? "center" :
                                 (i === 'valor' || i === '%' ) ? "right" : "left"
                },
                "flex": i === 'operacao' ? 3 : (i === 'range' ? 2 : 1),
                "minWidth": i === 'operacao' ? 200 : (i === 'range' ? 150 : (i === 'data' ? 110 : 70)),
                "valueFormatter": i === '%' ? {"function": "params.value === '***' ? '***' : Number(params.value).toFixed(2)"} :
                                 (i === 'valor' ? {"function": "params.value === '***' ? '***' : Math.round(params.value)"} : null)
            };
        });

        return [colDefs, colDefs];
    }
    """,
    Output('grid-classica', 'columnDefs'),
    Output('grid-agressiva', 'columnDefs'),
    Input('update-interval', 'n_intervals'),
    State('privacy-store', 'data')
)

if __name__ == '__main__':
    # Rodando externamente para que você possa abrir o link clássico no navegador
    app.run(jupyter_mode="external", host='0.0.0.0', port=8050, debug=True)