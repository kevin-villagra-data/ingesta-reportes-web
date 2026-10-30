"""Punto de entrada del job diario.

    python main.py --demo                       # bot + carga en SQLite local
    python main.py --demo --archivo reporte.csv # solo carga, sin bot
    python main.py                              # producción: SQL Server (SQLSERVER_CADENA)

Devuelve código de salida 1 ante cualquier error, para que el job de
SQL Server Agent quede marcado como fallido y avise.
"""
import argparse
import logging
import sqlite3
import sys

from bot.carga import (cargar_staging, consolidar, controlar_integridad, crear_tablas_demo,
                       validar_encabezado)
from bot.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("ingesta.log", encoding="utf-8")],
)
log = logging.getLogger("ingesta")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--demo", action="store_true", help="usa SQLite local en lugar de SQL Server")
    p.add_argument("--archivo", help="CSV ya descargado (saltea el bot)")
    args = p.parse_args()
    cfg = Config.desde_entorno()

    try:
        if args.archivo:
            ruta = args.archivo
        else:
            from bot.descarga import descargar_con_reintentos
            ruta = descargar_con_reintentos(cfg)

        validar_encabezado(ruta)

        if args.demo:
            con, dialecto = sqlite3.connect("demo.db"), "sqlite"
            crear_tablas_demo(con)
        else:
            import pyodbc
            con, dialecto = pyodbc.connect(cfg.cadena_sqlserver), "sqlserver"

        leidas = cargar_staging(con, ruta, dialecto=dialecto)
        controlar_integridad(con, leidas)
        nuevas = consolidar(con, dialecto)
        log.info("OK: %d filas leídas, %d nuevas en el histórico", leidas, nuevas)
        return 0
    except Exception:
        log.exception("La ingesta falló")
        return 1


if __name__ == "__main__":
    sys.exit(main())
