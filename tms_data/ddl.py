"""Render CREATE TABLE / CREATE VIEW statements for BigQuery, AlloyDB (PostgreSQL) and DuckDB.

    python -m tms_data.ddl --dialect bigquery --dataset my-project.mclane_tms > sql/bigquery_schema.sql
    python -m tms_data.ddl --dialect alloydb  --schema tms                 > sql/alloydb_schema.sql
"""

from __future__ import annotations

import argparse
import re

from tms_agent.schema import TABLES, VIEWS

TYPE_MAP = {
    "bigquery": {"STRING": "STRING", "INT": "INT64", "FLOAT": "FLOAT64", "NUMERIC": "NUMERIC", "BOOL": "BOOL",
                 "DATE": "DATE", "TIMESTAMP": "TIMESTAMP"},
    "alloydb": {"STRING": "TEXT", "INT": "INTEGER", "FLOAT": "DOUBLE PRECISION", "NUMERIC": "NUMERIC(14,2)",
                "BOOL": "BOOLEAN", "DATE": "DATE", "TIMESTAMP": "TIMESTAMP"},
    "duckdb": {"STRING": "VARCHAR", "INT": "INTEGER", "FLOAT": "DOUBLE", "NUMERIC": "DECIMAL(14,2)",
               "BOOL": "BOOLEAN", "DATE": "DATE", "TIMESTAMP": "TIMESTAMP"},
}

# Partition / cluster large BigQuery tables for cheap, fast agent queries.
BQ_LAYOUT = {
    "loads": ("load_date", "origin_dc_id, carrier_id"),
    "stops": ("delivery_date", "location_id, load_id"),
    "orders": ("requested_delivery_date", "customer_id"),
    "load_costs": ("cost_date", "load_id, cost_type"),
    "invoices": ("invoice_date", "customer_id"),
    "exceptions": ("event_date", "exception_type, severity"),
    "carrier_tenders": ("tender_date", "carrier_id"),
    "check_calls": ("DATE(event_ts)", "load_id"),
    "geofence_events": ("event_date", "location_id, load_id"),
}

# Secondary indexes for AlloyDB (the columnar engine accelerates the analytics on top).
PG_INDEXES = {
    "loads": ["load_date", "origin_dc_id", "carrier_id", "load_status"],
    "stops": ["load_id", "location_id", "delivery_date"],
    "orders": ["customer_id", "load_id"],
    "load_costs": ["load_id"],
    "invoices": ["order_id", "customer_id"],
    "exceptions": ["load_id", "event_date", "exception_type"],
    "carrier_tenders": ["load_id", "carrier_id"],
    "check_calls": ["load_id"],
    "geofence_events": ["stop_id", "location_id", "event_date"],
    "locations": ["customer_id", "dc_id"],
}


def _q(s: str) -> str:
    return s.replace("'", "\\'") if s else s


def render(dialect: str, prefix: str) -> str:
    types = TYPE_MAP[dialect]
    out: list[str] = []
    if dialect == "alloydb":
        schema = prefix.rstrip(".")
        out.append(f"CREATE SCHEMA IF NOT EXISTS {schema};\n")
    for t in TABLES:
        cols = []
        for c in t.columns:
            col = f"  {c.name} {types[c.type]}"
            if not c.nullable:
                col += " NOT NULL"
            if dialect == "bigquery":
                col += f" OPTIONS(description='{_q(c.description)}')"
            cols.append(col)
        if dialect != "bigquery" and t.primary_key:
            cols.append(f"  PRIMARY KEY ({t.primary_key})")
        name = f"`{prefix}{t.name}`" if dialect == "bigquery" else f"{prefix}{t.name}"
        ddl = f"CREATE TABLE IF NOT EXISTS {name} (\n" + ",\n".join(cols) + "\n)"
        if dialect == "bigquery":
            if t.name in BQ_LAYOUT:
                part, cluster = BQ_LAYOUT[t.name]
                ddl += f"\nPARTITION BY {part}\nCLUSTER BY {cluster}"
            ddl += f"\nOPTIONS(description='{_q(t.description)} TMW: {_q(t.tmw_equivalent)}')"
        out.append(ddl + ";\n")
        if dialect == "alloydb":
            out.append(f"COMMENT ON TABLE {prefix}{t.name} IS '{t.description.replace(chr(39), chr(39) * 2)}';")
            for c in t.columns:
                out.append(f"COMMENT ON COLUMN {prefix}{t.name}.{c.name} IS '{c.description.replace(chr(39), chr(39) * 2)}';")
            for col in PG_INDEXES.get(t.name, []):
                out.append(f"CREATE INDEX IF NOT EXISTS ix_{t.name}_{col} ON {prefix}{t.name} ({col});")
            out.append("")
    for name, sql in VIEWS.items():
        p = f"`{prefix.rstrip('.')}`." if dialect == "bigquery" else prefix
        body = sql.replace("{p}", p).strip()
        if dialect == "bigquery":
            body = re.sub(r"`([^`]+)`\.(\w+)", r"`\1.\2`", body)
            out.append(f"CREATE OR REPLACE VIEW `{prefix}{name}` AS\n{body};\n")
        else:
            out.append(f"CREATE OR REPLACE VIEW {prefix}{name} AS\n{body};\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dialect", choices=list(TYPE_MAP), required=True)
    ap.add_argument("--dataset", help="BigQuery project.dataset", default="YOUR_PROJECT.mclane_tms")
    ap.add_argument("--schema", help="AlloyDB / DuckDB schema", default="tms")
    a = ap.parse_args()
    prefix = f"{a.dataset}." if a.dialect == "bigquery" else (f"{a.schema}." if a.dialect == "alloydb" else "")
    print(render(a.dialect, prefix))


if __name__ == "__main__":
    main()
