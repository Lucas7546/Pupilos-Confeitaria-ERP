"""
previsao.py — módulo depreciado.

A lógica de previsão de demanda foi consolidada em `modules/estoque.py`
na função `previsao_demanda()`, que é a fonte única de verdade.

Este arquivo existe apenas para não quebrar importações antigas em app.py.
Remova-o após atualizar app.py para importar diretamente de estoque.
"""

from modules.estoque import previsao_demanda  # noqa: F401  (reexportado)


def prever_consumo_materia_prima(dias_previsao: int = 7):
    """
    DEPRECIADO — use `from modules.estoque import previsao_demanda`.
    Mantido por compatibilidade com o app.py atual.
    """
    return previsao_demanda()
