from db import get_conn
from utils.logger import log_erro
import datetime


def registrar_log(acao: str, modulo: str, detalhe: str, usuario: str = None):
    """
    AUDITORIA DO ERP (nível negócio)
    """

    try:
        with get_conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO logs (usuario, acao, modulo, detalhe, data)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        usuario,
                        acao,
                        modulo,
                        detalhe,
                        datetime.datetime.now()
                    )
                )
            con.commit()

    except Exception as e:
        log_erro(f"Falha ao registrar auditoria: {e}")