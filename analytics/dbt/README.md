# dbt read-model quality boundary

This project is downstream of the canonical event/source authority. It is deliberately not a collector, classifier, canonical-ID generator, or publication database.

Flow:

```text
canonical ledger / occurrence contracts
  -> generated SQLite read model (#158 contract)
  -> dbt source("canonical_read_model", ...)
  -> staging + analytical marts + data tests
  -> operator artifacts / analytical lineage
```

The first slice uses a deterministic SQLite schema fixture instead of production data because #158 is not yet merged. The fixture is contract evidence, not a copied production dataset.

## Run

Install the SQLite adapter and execute the repository verifier:

```bash
python -m pip install "dbt-sqlite==1.10.0"
python scripts/verify_dbt_read_model_contract.py
```

The verifier runs a healthy fixture twice, proves logical output determinism, and proves that duplicate source identity, orphan event links, and invalid decision values fail dbt tests.

dbt writes only to a separate analytics SQLite database. The canonical input database is hashed before and after every dbt build and any mutation fails verification.

Generated dbt artifacts stay under `analytics/dbt/target/` and are CI/operator artifacts only. They are not copied into `public/`.
