"""Read-only integrity audit of the configured database against the configured ledger."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id', help='Audit one batch; omit to audit every batch.')
    parser.add_argument('--database', type=Path, help='Existing SQLite file. Default: backend configuration.')
    parser.add_argument('--json', action='store_true', help='Print the complete machine-readable report.')
    args = parser.parse_args(argv)
    if args.database:
        database = args.database.expanduser().resolve()
        if not database.is_file():
            parser.error(f'Database does not exist: {database}')
        os.environ['DATABASE_URL'] = f'sqlite:///{database.as_posix()}'
    sys.path.insert(0, str(ROOT / 'backend'))
    from app import config
    from app.db import SessionLocal
    from app.models import Batch
    from app.services.ledger import get_ledger
    from app.services.verify import verify_batch
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    database_url = make_url(config.DATABASE_URL)
    if database_url.drivername.startswith('sqlite') and database_url.database != ':memory:':
        if not database_url.database or not Path(database_url.database).is_file():
            parser.error('Configured SQLite database does not exist. Start the application first.')
    try:
        ledger = get_ledger()
        network = ledger.network_info()
        with SessionLocal() as db:
            if database_url.drivername.startswith('sqlite'):
                db.execute(text('PRAGMA query_only=ON'))
            batches = db.query(Batch).order_by(Batch.batch_id).all()
            if args.batch_id:
                batches = [batch for batch in batches if batch.batch_id == args.batch_id]
            if not batches:
                parser.error('No matching batch exists in this database.')
            reports = [verify_batch(db, batch.batch_id) for batch in batches]
        if args.json:
            print(json.dumps({'network':network, 'batches':reports}, ensure_ascii=False, indent=2))
        else:
            print(f"Ledger: {network['network']} | mode={network['mode']} | chainId={network['chainId']}")
            if network['mode'] == 'mock':
                print('Local database ledger; this is not independent Avalanche evidence.')
            for result in reports:
                mismatches = [segment['eventId'] for segment in result['segments'] if not segment['match']]
                print(f"{result['batchId']}: {result['overall']} | events={result['eventCount']} | "
                      f"mismatchedSegments={len(mismatches)} | signatureFailures={result['signatureFailureCount']}")
                for segment in result['segments']:
                    if not segment['match']:
                        print(f"  {segment['eventId']}: stored={segment['onChainDataHash']} recomputed={segment['recomputedHash']}")
                for issue in result['chainIssues']:
                    print(f"  {issue['eventId']}: {issue['issue']}")
        return 0 if all(result['overall'] == 'PASS' for result in reports) else 1
    except Exception as exc:
        print(f'Audit could not complete: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
