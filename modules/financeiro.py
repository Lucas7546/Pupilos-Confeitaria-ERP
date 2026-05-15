from modules.db import conectar


# =========================================================
# 1. FINANCEIRO BASE (30 dias)
# =========================================================
def calcular_financeiro(periodo_dias=30):
    con = conectar()
    cur = con.cursor()

    # =====================================================
    # FATURAMENTO
    # =====================================================
    cur.execute("""
        SELECT COALESCE(SUM(valor_total), 0)
        FROM vendas
        WHERE data_venda >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))

    faturamento = float(cur.fetchone()[0] or 0)

    # =====================================================
    # CUSTO INSUMOS (CORRIGIDO JOIN)
    # =====================================================
    cur.execute("""
        SELECT COALESCE(SUM(i.quantidade * mp.preco_unitario), 0)
        FROM itens_venda i
        JOIN produtos p ON p.id_produto = i.id_produto
        JOIN receitas r ON r.id_produto = p.id_produto
        JOIN materia_prima mp ON mp.id_materia_prima = r.id_materia_prima
    """)

    custo_insumos = float(cur.fetchone()[0] or 0)

    # =====================================================
    # DESPESAS FIXAS
    # =====================================================
    cur.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM despesas
        WHERE data_despesa >= CURRENT_DATE - INTERVAL %s
    """, (f"{periodo_dias} days",))

    total_fixas = float(cur.fetchone()[0] or 0)

    con.close()

    lucro_base = faturamento - custo_insumos - total_fixas

    return {
        "faturamento": faturamento,
        "custo_insumos": custo_insumos,
        "total_fixas": total_fixas,
        "lucro_base": lucro_base
    }


# =========================================================
# 2. CONFIG EMPRESA (REGIME FISCAL)
# =========================================================
def get_config_empresa():
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        SELECT regime_fiscal
        FROM empresa_config
        ORDER BY id ASC
        LIMIT 1
    """)

    result = cur.fetchone()
    con.close()

    return result[0] if result else "MEI"


# =========================================================
# 3. ATUALIZAR REGIME FISCAL
# =========================================================
def atualizar_regime_fiscal(novo_regime):
    con = conectar()
    cur = con.cursor()

    cur.execute("""
        UPDATE empresa_config
        SET regime_fiscal = %s
        WHERE id = (
            SELECT id FROM empresa_config ORDER BY id ASC LIMIT 1
        )
    """, (novo_regime,))

    con.commit()
    con.close()


# =========================================================
# 4. CÁLCULO DE IMPOSTO
# =========================================================
def calcular_imposto(faturamento):
    regime = get_config_empresa()

    if regime == "MEI":
        aliquota = 0.04
    elif regime == "ME":
        aliquota = 0.08
    elif regime in ["SN", "SIMPLES"]:
        aliquota = 0.12
    else:
        aliquota = 0.10

    return faturamento * aliquota


# =========================================================
# 5. FINANCEIRO COMPLETO (TELA PRINCIPAL)
# =========================================================
def calcular_financeiro_com_imposto(periodo_dias=30):
    base = calcular_financeiro(periodo_dias)

    faturamento = base["faturamento"]
    imposto = calcular_imposto(faturamento)
    regime = get_config_empresa()

    lucro_final = base["lucro_base"] - imposto

    return {
        **base,
        "imposto": imposto,
        "regime": regime,
        "lucro_final": lucro_final
    }