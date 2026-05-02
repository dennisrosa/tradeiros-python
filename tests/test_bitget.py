import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
from tradeiros.bitget.bitget import Bitget

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "BITGET_API_KEY": "test_key",
        "BITGET_API_SECRET": "test_secret",
        "BITGET_PASSPHRASE": "test_passphrase"
    }):
        yield

@pytest.fixture
def bitget_instance(mock_env):
    with patch("ccxt.bitget") as mock_ccxt:
        mock_instance = MagicMock()
        mock_ccxt.return_value = mock_instance
        yield Bitget()

def test_bitget_initialization_success(mock_env):
    with patch("ccxt.bitget") as mock_ccxt:
        bitget = Bitget()
        mock_ccxt.assert_called_once_with({
            'apiKey': 'test_key',
            'secret': 'test_secret',
            'password': 'test_passphrase',
            'options': {'defaultType': 'swap'}
        })
        assert bitget.instance is not None

def test_bitget_initialization_missing_env():
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="As credenciais da Bitget não foram fornecidas"):
            Bitget()

def test_bitget_get_btc_preco(bitget_instance):
    bitget_instance.instance.fetch_ticker.return_value = {"last": "60000.0"}
    price = bitget_instance.get_btc_preco()
    bitget_instance.instance.fetch_ticker.assert_called_with('BTC/USD:BTC')
    assert price == 60000.0

def test_bitget_get_patrimonio(bitget_instance):
    # Mock fetch_balance
    bitget_instance.instance.fetch_balance.return_value = {
        'BTC': {'total': 0.1}
    }
    # Mock get_btc_preco
    with patch.object(Bitget, 'get_btc_preco', return_value=60000.0):
        patrimonio = bitget_instance.get_patrimonio()

    bitget_instance.instance.fetch_balance.assert_called_with({'productType': 'COIN-FUTURES'})
    assert patrimonio == 6000.0 # 0.1 * 60000

def test_bitget_get_margem_disponivel(bitget_instance):
    bitget_instance.instance.fetch_balance.return_value = {
        'BTC': {'total': 0.1, 'free': 0.05}
    }

    margem = bitget_instance.get_margem_disponivel()

    bitget_instance.instance.fetch_balance.assert_called_with({'productType': 'COIN-FUTURES'})
    assert margem == 0.05

def test_bitget_get_margem_disponivel_error(bitget_instance):
    bitget_instance.instance.fetch_balance.side_effect = Exception("API error")

    margem = bitget_instance.get_margem_disponivel()
    assert margem == 0.0

def test_bitget_get_ordens(bitget_instance):
    # Mock fetch_open_orders side effect for Limit and Plan orders
    bitget_instance.instance.fetch_open_orders.side_effect = [
        # Call 1: Limit orders
        [
            {'symbol': 'BTC/USD:BTC', 'type': 'limit', 'side': 'buy', 'price': 50000.0, 'amount': 0.001, 'id': '1', 'timestamp': 1710460800000}
        ],
        # Call 2: Plan orders
        [
            {'symbol': 'BTC/USD:BTC', 'type': 'market', 'side': 'sell', 'stopPrice': 55000.0, 'amount': 0.002, 'id': '2', 'timestamp': 1710464400000}
        ]
    ]
    
    with patch.object(Bitget, 'get_btc_preco', return_value=60000.0):
        df = bitget_instance.get_ordens()
    
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    # Order 1: 0.001 * 50000 = 50.0
    # Order 2: 0.002 * 55000 = 110.0
    assert 50.0 in df['qtd'].values
    assert 110.0 in df['qtd'].values

def test_bitget_get_short_protecao(bitget_instance):
    # Mock fetch_positions
    bitget_instance.instance.fetch_positions.return_value = [
        {'symbol': 'BTC/USD:BTC', 'contracts': 0.01, 'side': 'short'}
    ]
    
    with patch.object(Bitget, 'get_btc_preco', return_value=60000.0):
        short = bitget_instance.get_short_protecao()
    
    # Val USD = 0.01 * 60000 = 600.0. Short is -600.0
    assert short == -600.0

def test_bitget_consolidate(bitget_instance):
    data = {
        'par': ['BTC', 'BTC'],
        'tipo': ['limit', 'limit'],
        'operacao': ['buy', 'buy'],
        'preco': [50000.0, 50100.0],
        'qtd': [10.0, 10.0],
        'reduce': ['false', 'false'],
        'data_criacao': ['14/03 10:00', '14/03 10:10']
    }
    df = pd.DataFrame(data)
    
    allocation = 1000.0
    btc_price = 60000.0
    short_thp = -100.0
    
    result = bitget_instance.consolidate(df, allocation, btc_price, short_thp)
    
    assert len(result) == 2 # 1 group + 1 protected row
    # Limit row: sum(10+10) = 20. % = 20 * 100 / 1000 = 2.0
    limit_row = result[result['tipo'] == 'limit'].iloc[0]
    assert limit_row['qtd_sum'] == 20.0
    assert limit_row['%'] == 2.0
    
    # Protected row: qtd_sum = -100.0. % = |-100| * 100 / 1000 = 10.0
    prot_row = result[result['tipo'] == 'protected'].iloc[0]
    assert prot_row['qtd_sum'] == -100.0
    assert prot_row['%'] == 10.0

def test_bitget_atualizar(bitget_instance):
    # Mock all internal calls
    with patch.object(Bitget, 'get_btc_preco', return_value=60000.0), \
         patch.object(Bitget, 'get_patrimonio', return_value=10000.0), \
         patch.object(Bitget, 'get_ordens', return_value=pd.DataFrame()), \
         patch.object(Bitget, 'get_short_protecao', return_value=-500.0), \
         patch.object(Bitget, 'consolidate') as mock_cons:
        
        mock_cons.return_value = pd.DataFrame({'result': ['success']})
        
        df, pat = bitget_instance.atualizar()
        
        assert pat == 10000.0
        assert not df.empty
        mock_cons.assert_called_once()
