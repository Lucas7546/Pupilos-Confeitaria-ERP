from contextlib import contextmanager
from flask import g
from modules.db import _get_pool


@contextmanager
def get_conn():

    empresa_id = getattr(
        g,
        "empresa_id",
        None
    )

    if empresa_id is None:
        raise Exception(
            "Tenant não definido"
        )

    pool = _get_pool()
    conn = pool.getconn()

    try:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT set_config(
                    'app.empresa_id',
                    %s,
                    false
                )
                """,
                (str(empresa_id),)
            )

        yield conn

        conn.commit()

    except Exception:

        conn.rollback()
        raise

    finally:

        pool.putconn(conn)