"""Create the schema and load generated CSVs into DuckDB, BigQuery or AlloyDB.

    python -m tms_data.load --target duckdb   --csv data/generated --duckdb data/tms.duckdb
    python -m tms_data.load --target bigquery --csv data/generated --project $GOOGLE_CLOUD_PROJECT --dataset mclane_tms
    python -m tms_data.load --target alloydb  --csv data/generated --dsn "postgresql://postgres:PW@127.0.0.1:5432/postgres"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tms_agent.schema import TABLES
from tms_data.ddl import TYPE_MAP, render


def _statements(sql: str) -> list[str]:
    return [s.strip() for s in sql.split(";\n") if s.strip() and not s.strip().startswith("--")]


def load_duckdb(csv_dir: Path, db_path: Path) -> dict[str, int]:
    import duckdb

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    ddl = render("duckdb", "")
    tables_ddl = ddl.split("CREATE OR REPLACE VIEW")[0]
    for stmt in _statements(tables_ddl):
        con.execute(stmt)
    counts = {}
    for t in TABLES:
        types = {c.name: TYPE_MAP["duckdb"][c.type] for c in t.columns}
        con.execute(
            f"INSERT INTO {t.name} SELECT * FROM read_csv(?, header=true, columns=?, nullstr='')",
            [str(csv_dir / f"{t.name}.csv"), types],
        )
        counts[t.name] = con.execute(f"SELECT COUNT(*) FROM {t.name}").fetchone()[0]
    for view in ddl.split("CREATE OR REPLACE VIEW")[1:]:
        con.execute("CREATE OR REPLACE VIEW" + view.rstrip().rstrip(";"))
    con.close()
    return counts


def load_bigquery(csv_dir: Path, project: str, dataset: str, location: str = "US") -> dict[str, int]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(f"{project}.{dataset}")
    ds.location = location
    ds.description = "Synthetic Trimble TMW-style TMS data for the TMS Intelligence agent."
    client.create_dataset(ds, exists_ok=True)
    for t in TABLES:
        client.delete_table(f"{project}.{dataset}.{t.name}", not_found_ok=True)
    for stmt in _statements(render("bigquery", f"{project}.{dataset}.")):
        client.query(stmt).result()
    counts = {}
    for t in TABLES:
        cfg = bigquery.LoadJobConfig(source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1,
                                     null_marker="", write_disposition="WRITE_TRUNCATE")
        with (csv_dir / f"{t.name}.csv").open("rb") as fh:
            client.load_table_from_file(fh, f"{project}.{dataset}.{t.name}", job_config=cfg).result()
        counts[t.name] = client.get_table(f"{project}.{dataset}.{t.name}").num_rows
    return counts


def load_alloydb(csv_dir: Path, dsn: str, schema: str = "tms") -> dict[str, int]:
    import psycopg

    counts = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        for stmt in _statements(render("alloydb", f"{schema}.")):
            conn.execute(stmt)
        for t in TABLES:
            cols = ", ".join(t.column_names)
            with conn.cursor() as cur, cur.copy(
                f"COPY {schema}.{t.name} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)"
            ) as cp, (csv_dir / f"{t.name}.csv").open("rb") as fh:
                while chunk := fh.read(1 << 20):
                    cp.write(chunk)
            counts[t.name] = conn.execute(f"SELECT COUNT(*) FROM {schema}.{t.name}").fetchone()[0]
        conn.execute(f"ANALYZE")
    return counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["duckdb", "bigquery", "alloydb"], required=True)
    ap.add_argument("--csv", default="data/generated", type=Path)
    ap.add_argument("--duckdb", default="data/tms.duckdb", type=Path)
    ap.add_argument("--project")
    ap.add_argument("--dataset", default="mclane_tms")
    ap.add_argument("--location", default="US")
    ap.add_argument("--dsn", help="PostgreSQL DSN for AlloyDB (via Auth Proxy or private IP)")
    ap.add_argument("--schema", default="tms")
    a = ap.parse_args()
    if a.target == "duckdb":
        counts = load_duckdb(a.csv, a.duckdb)
    elif a.target == "bigquery":
        counts = load_bigquery(a.csv, a.project, a.dataset, a.location)
    else:
        counts = load_alloydb(a.csv, a.dsn, a.schema)
    for k, v in counts.items():
        print(f"{k:16s} {v:>8,d}")


if __name__ == "__main__":
    main()
