from abc import ABC, abstractmethod

class ExchangeBase(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def get_patrimonio(self):
        pass

    @abstractmethod
    def get_btc_preco(self):
        pass

    @abstractmethod
    def get_ordens(self):
        pass

    @abstractmethod
    def get_short_protecao(self):
        pass

    @abstractmethod
    def get_margem_disponivel(self):
        pass

    @abstractmethod
    def get_alavancagem(self):
        pass

    @abstractmethod
    def atualizar(self):
        pass
