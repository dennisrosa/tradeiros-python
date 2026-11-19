import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
import json
from tradeiros.okx.okx import Okx

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "OKX_API_KEY": "test_key",
        "OKX_API_SECRET": "test_secret",
        "OKX_PASSPHRASE": "test_passphrase",
        "OKX_FLAG": "0"
    }):
        yield

@pytest.fixture
def okx_instance(mock_env):
    with patch("okx.Account.AccountAPI"), \
         patch("okx.Trade.TradeAPI"), \
         patch("okx.MarketData.MarketAPI"):
        return Okx()

def test_okx_initialization_success(mock_env):
    with patch("okx.Account.AccountAPI") as mock_acc, \
         patch("okx.Trade.TradeAPI") as mock_trade, \
         patch("okx.MarketData.MarketAPI") as mock_market:
        
        okx = Okx()
        
        mock_acc.assert_called_once_with(
            api_key="test_key",
            api_secret_key="test_secret",
            passphrase="test_passphrase",
            flag="0",
            debug=False
        )
        assert okx.account is not None
        assert okx.trade is not None
        assert okx.market is not None

def test_okx_initialization_missing_env():
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="As credenciais da OKX não foram fornecidas"):
            Okx()

def test_okx_get_btc_preco(okx_instance):
    okx_instance.market.get_ticker.return_value = {
        "code": "0",
        "data": [{"last": "55000.0"}]
    }
    
    price = okx_instance.get_btc_preco()
    
    okx_instance.market.get_ticker.assert_called_with(instId='BTC-USD-SWAP')
    assert price == 55000.0

def test_okx_get_patrimonio(okx_instance):
    # Mock balance response
    okx_instance.account.get_account_balance.return_value = {
        "data": [{
            "details": [
                {"ccy": "USDT", "eq": "100"},
                {"ccy": "BTC", "eq": "0.5"}
            ]
        }]
    }

    # Mock price
    with patch.object(Okx, 'get_btc_preco', return_value=50000.0):
        patrimonio = okx_instance.get_patrimonio()

    okx_instance.account.get_account_balance.assert_called_with(ccy='BTC')
    # eq (0.5) * price (50000.0) = 25000.0
    assert patrimonio == 25000.0

def test_okx_get_margem_disponivel(okx_instance):
    okx_instance.account.get_account_balance.return_value = {
        "data": [{
            "details": [
                {"ccy": "BTC", "availBal": "0.25", "eq": "0.5"}
            ]
        }]
    }

    margem = okx_instance.get_margem_disponivel()

    okx_instance.account.get_account_balance.assert_called_with(ccy='BTC')
    assert margem == 0.25

def test_okx_get_margem_disponivel_empty(okx_instance):
    okx_instance.account.get_account_balance.return_value = {
        "data": [{
            "details": []
        }]
    }

    margem = okx_instance.get_margem_disponivel()
    assert margem == 0.0

def test_okx_get_margem_disponivel_error(okx_instance):
    okx_instance.account.get_account_balance.return_value = {"code": "1", "msg": "error"}

    margem = okx_instance.get_margem_disponivel()
    assert margem == 0.0

def test_okx_get_short_protecao(okx_instance):
    okx_instance.account.get_positions.return_value = {
        "data": [
            {"posSide": "long", "pos": "9.8"},
            {"posSide": "short", "pos": "14.7"},
            {"posSide": "net", "pos": "0"},
        ]
    }

    pos = okx_instance.get_short_protecao()

    okx_instance.account.get_positions.assert_called_with(instId='BTC-USD-SWAP')
    assert pos == -14.7

def test_okx_get_posicoes(okx_instance):
    okx_instance.account.get_positions.return_value = {
        "data": [
            {"posSide": "long", "pos": "9.8", "avgPx": "65000", "uTime": "1794960616824"},
            {"posSide": "short", "pos": "14.7", "avgPx": "65400", "uTime": "1794960642723"},
            {"posSide": "net", "pos": "0"},
        ]
    }

    df = okx_instance.get_posicoes()

    assert len(df) == 2
    long_row = df[df['operacao'] == 'buy'].iloc[0]
    short_row = df[df['operacao'] == 'sell'].iloc[0]
    assert long_row['qtd'] == 9.8
    assert short_row['qtd'] == -14.7
    assert long_row['preco'] == 65000.0
    assert set(df['tipo']) == {'long', 'short'}

def test_load_limit_orders_okx(okx_instance):
    okx_instance.trade.get_order_list.return_value = {
        "data": [
            {"instId": "BTC-USD-SWAP", "ordType": "limit", "px": "50000", "reduceOnly": "false", "side": "buy", "sz": "1", "cTime": "1710460800000"}
        ]
    }
    
    df = okx_instance.load_limit_orders_okx()
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]['preco'] == 50000.0
    assert df.iloc[0]['qtd'] == 1.0

def test_load_market_orders_okx(okx_instance):
    okx_instance.trade.order_algos_list.return_value = {
        "data": [
            {"instId": "BTC-USD-SWAP", "ordType": "limit", "slTriggerPx": "45000", "reduceOnly": "true", "side": "sell", "sz": "2", "cTime": "1710464400000"}
        ]
    }
    
    df = okx_instance.load_market_orders_okx()
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.iloc[0]['preco'] == 45000.0
    assert df.iloc[0]['qtd'] == 2.0

def test_get_ordens(okx_instance):
    with patch.object(Okx, 'load_limit_orders_okx') as mock_limit, \
         patch.object(Okx, 'load_market_orders_okx') as mock_market:
        
        mock_limit.return_value = pd.DataFrame([{'preco': 50000.0}])
        mock_market.return_value = pd.DataFrame([{'preco': 45000.0}])
        
        df = okx_instance.get_ordens()
        
        assert len(df) == 2
        # sorted ascending
        assert df.iloc[0]['preco'] == 45000.0
        assert df.iloc[1]['preco'] == 50000.0

def test_consolidate(okx_instance):
    data = {
        'par': ['BTC', 'BTC'],
        'tipo': ['limit', 'limit'],
        'operacao': ['buy', 'buy'],
        'preco': [50000.0, 50100.0],
        'qtd': [1.0, 1.0],
        'reduce': ['false', 'false'],
        'data_criacao': ['14/03 10:00', '14/03 10:10']
    }
    df = pd.DataFrame(data)
    
    allocation = 100000.0
    btc_price = 50000.0
    short_thp = -0.1
    
    result = okx_instance.consolidate(df, allocation, btc_price, short_thp)
    
    assert isinstance(result, pd.DataFrame)
    # Check if short row was added
    assert any(result['tipo'] == 'short')
    # Check row count: 1 group (limit buy) + 1 short = 2
    assert len(result) == 2
    # Checked percentage calculation for group: qtd_sum(1+1)*100 * 100 / allocation = 200 * 100 / 100000 = 0.2
    group_row = result[result['tipo'] == 'limit'].iloc[0]
    assert group_row['%'] == 0.2    # Wait: result['qtd_sum'] = agrupado['qtd_sum'] * 100 -> if sum was 2, it becomes 200.
    # % = 200 * 100 / 100000 = 0.2. 
    # Local check: 200 * 100 / 100000 = 20000 / 100000 = 0.2.

def test_consolidate_separa_reduce_e_posside(okx_instance):
    data = {
        'par': ['BTC', 'BTC', 'BTC', 'BTC'],
        'tipo': ['limit', 'limit', 'limit', 'limit'],
        'operacao': ['buy', 'buy', 'buy', 'buy'],
        'preco': [62063.7, 62096.7, 62262.3, 62244.7],
        'qtd': [0.5, 0.6, 0.5, 0.5],
        'reduce': ['true', 'false', 'true', 'false'],
        'posSide': ['short', 'long', 'short', 'long'],
        'data_criacao': ['15/11 03:47', '15/11 03:47', '15/11 03:47', '15/11 03:47'],
    }
    df = pd.DataFrame(data)

    result = okx_instance.consolidate(df, 100000.0, 65000.0, posicoes=None, short_thp=-0.1)

    orders = result[result['tipo'] == 'limit']
    # Deve separar em 2 grupos: reduce=false (long) e reduce=true (short)
    assert len(orders) == 2
    assert set(orders['reduce']) == {'true', 'false'}

def test_consolidate_separa_blocos_de_preco(okx_instance):
    # Mesmo tipo/lado/reduce/posSide, mas dois blocos de preço bem separados
    precos = [76000, 75500, 75000, 74500, 74000, 73500, 73000, 72500, 72000, 71500,
              68000, 67500]
    data = {
        'par': ['BTC'] * 12,
        'tipo': ['limit'] * 12,
        'operacao': ['sell'] * 12,
        'preco': precos,
        'qtd': [1.0] * 12,
        'reduce': ['false'] * 12,
        'posSide': ['short'] * 12,
        'data_criacao': ['15/11 03:47'] * 12,
    }
    df = pd.DataFrame(data)

    result = okx_instance.consolidate(df, 1000000.0, 65000.0)

    sells = result[result['tipo'] == 'limit']
    assert len(sells) == 2
    assert sorted(sells['qtd_ordens'].tolist()) == [2, 10]

def test_consolidate_com_posicoes(okx_instance):
    posicoes = pd.DataFrame([
        {'par': 'BTC-USD-SWAP', 'tipo': 'long', 'operacao': 'buy', 'preco': 65858.41, 'qtd': 9.8, 'reduce': 'false', 'data_criacao': '15/11 03:47'},
        {'par': 'BTC-USD-SWAP', 'tipo': 'short', 'operacao': 'sell', 'preco': 65418.99, 'qtd': -14.7, 'reduce': 'false', 'data_criacao': '15/11 03:47'},
    ])
    df = pd.DataFrame([{
        'par': 'BTC', 'tipo': 'limit', 'operacao': 'buy', 'preco': 62000.0,
        'qtd': 1.0, 'reduce': 'false', 'posSide': 'long', 'data_criacao': '15/11 03:47'
    }])

    result = okx_instance.consolidate(df, 100000.0, 65000.0, posicoes=posicoes)

    protected = result[result['tipo'].isin(['long', 'short'])]
    assert len(protected) == 2
    long_row = protected[protected['tipo'] == 'long'].iloc[0]
    short_row = protected[protected['tipo'] == 'short'].iloc[0]
    assert long_row['qtd_sum'] == pytest.approx(980.0)
    assert short_row['qtd_sum'] == pytest.approx(-1470.0)
    
def test_atualizar(okx_instance):
    with patch.object(Okx, 'get_ordens') as mock_orders, \
         patch.object(Okx, 'get_patrimonio', return_value=100000.0), \
         patch.object(Okx, 'get_btc_preco', return_value=50000.0), \
         patch.object(Okx, 'get_posicoes', return_value=pd.DataFrame()), \
         patch.object(Okx, 'consolidate') as mock_cons:
        
        mock_orders.return_value = pd.DataFrame()
        mock_cons.return_value = pd.DataFrame({'status': ['ok']})
        
        res_df, res_patrimonio = okx_instance.atualizar()
        
        mock_orders.assert_called_once()
        mock_cons.assert_called_once()
        assert not res_df.empty
        assert res_patrimonio == 100000.0
