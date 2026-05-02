import pytest
from unittest.mock import patch, MagicMock
from tradeiros.Tradeiros import Tradeiros

def test_tradeiros_initialization_okx():
    with patch("tradeiros.Tradeiros.Okx") as MockOkx:
        mock_instance = MagicMock()
        MockOkx.return_value = mock_instance
        
        tradeiros = Tradeiros("okx")
        
        MockOkx.assert_called_once()
        assert tradeiros.exchange == mock_instance

def test_tradeiros_initialization_bybit():
    with patch("tradeiros.Tradeiros.Bybit") as MockBybit:
        mock_instance = MagicMock()
        MockBybit.return_value = mock_instance
        
        tradeiros = Tradeiros("bybit")
        
        MockBybit.assert_called_once()
        assert tradeiros.exchange == mock_instance

def test_tradeiros_initialization_bitget():
    with patch("tradeiros.Tradeiros.Bitget") as MockBitget:
        mock_instance = MagicMock()
        MockBitget.return_value = mock_instance
        
        tradeiros = Tradeiros("bitget")
        
        MockBitget.assert_called_once()
        assert tradeiros.exchange == mock_instance

def test_tradeiros_initialization_invalid_exchange():
    with pytest.raises(ValueError, match="Exchange não suportada"):
        Tradeiros("binance")

def test_tradeiros_atualizar():
    with patch("tradeiros.Tradeiros.Okx") as MockOkx:
        mock_instance = MagicMock()
        mock_instance.atualizar.return_value = (MagicMock(), 1000.0)
        MockOkx.return_value = mock_instance

        tradeiros = Tradeiros("okx")
        df = tradeiros.atualizar()

        mock_instance.atualizar.assert_called_once()
        assert tradeiros.patrimonio() == 1000.0

def test_tradeiros_get_margem_disponivel():
    with patch("tradeiros.Tradeiros.Okx") as MockOkx:
        mock_instance = MagicMock()
        mock_instance.get_margem_disponivel.return_value = 0.25
        MockOkx.return_value = mock_instance

        tradeiros = Tradeiros("okx")
        margem = tradeiros.get_margem_disponivel()

        mock_instance.get_margem_disponivel.assert_called_once()
        assert margem == 0.25
