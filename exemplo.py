from tradeiros import Tradeiros

# Inicialize para a exchange desejada ("okx" ou "bitget")
tradeiros = Tradeiros("okx")

# Recupere os dados consolidados e exiba os resultados
df = tradeiros.atualizar()

# Exiba o DataFrame e o Patrimônio consolidado
print(df)
print(f"Patrimônio Total: {tradeiros.patrimonio():.8f}")
print(f"1% do patrimônio: {tradeiros.patrimonio() * 0.01:.8f}")