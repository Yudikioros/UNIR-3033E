"""Controlled Prisma deploy, with SQLite backup and baseline of the known legacy schema.

No application writes should run concurrently. Tests use --database on disposable copies.
"""
import argparse
from datetime import datetime, timezone
import pathlib
import shutil
import sqlite3
from contextlib import closing
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
BASELINE = "202609050001_legacy_baseline"
STATUS = {"BORRADOR": "DRAFT", "EN REVISIÓN": "UNDER_REVIEW", "MODIFICADO": "MODIFIED",
          "REGENERADO": "REGENERATED", "RECHAZADO": "REJECTED", "PLAN APROBADO": "APPROVED"}
LEGACY_COLUMNS = {
    "Patient": {"id", "name", "age", "gender", "goal", "pathologies", "createdAt"},
    "DietPlan": {"id", "patientId", "tdee_calculated", "plan_json", "status", "createdAt"},
}


def run_prisma(*args):
    subprocess.run(["uv", "run", "--no-sync", "prisma", *args], cwd=ROOT, check=True)


def preservation_queries(db):
    columns = {r['name'] for r in db.execute('PRAGMA table_info(Patient)')}
    if 'goal' in columns:
        return ('SELECT id,name,age,gender,goal,pathologies,createdAt FROM Patient',
                'SELECT id,patientId,tdee_calculated,plan_json,status,createdAt FROM DietPlan')
    return (
        "SELECT p.id,p.name,p.age,p.gender,s.originalGoal AS goal,s.originalPathologies AS pathologies,p.createdAt FROM Patient p LEFT JOIN LegacyPatientSnapshot s ON s.patientId=p.id",
        "SELECT d.id,c.patientId,s.originalTdee AS tdee_calculated,s.originalPlanJson AS plan_json,d.status,d.createdAt FROM DietPlan d JOIN NutritionConsultation c ON c.id=d.consultationId LEFT JOIN LegacyPlanSnapshot s ON s.dietPlanId=d.id",
    )


def migrate(database: pathlib.Path):
    database = database.resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    old_patients, old_plans = [], []
    baseline_required = False
    if database.exists():
        with closing(sqlite3.connect(database)) as db:
            db.row_factory = sqlite3.Row
            backup = database.with_name(database.stem + '-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.db')
            with closing(sqlite3.connect(backup)) as dest:
                db.backup(dest)
            print(f"Backup: {backup}", flush=True)
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('SQLite integrity check failed; no migration applied')
            if db.execute('PRAGMA foreign_key_check').fetchall():
                raise RuntimeError('Existing foreign key violations; no migration applied')
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'Patient' in tables:
                patient_query, plan_query = preservation_queries(db)
                old_patients = [dict(r) for r in db.execute(patient_query)]
                old_plans = [dict(r) for r in db.execute(plan_query)]
                for row in old_plans:
                    if row['status'] not in STATUS and row['status'] not in STATUS.values():
                        raise RuntimeError('Unknown legacy plan status; explicit mapping required')
                baseline_required = '_prisma_migrations' not in tables
                if baseline_required:
                    if tables - {'Patient', 'DietPlan', 'sqlite_sequence'}:
                        raise RuntimeError('Unknown unversioned tables; manual baseline review required')
                    for table, columns in LEGACY_COLUMNS.items():
                        actual = {r['name'] for r in db.execute(f'PRAGMA table_info("{table}")')}
                        if actual != columns:
                            raise RuntimeError(f'Unexpected legacy schema in {table}; no migration applied')
    with tempfile.TemporaryDirectory(prefix='alimentia-migrate-') as directory:
        work = pathlib.Path(directory)
        shutil.copytree(ROOT/'migrations', work/'migrations')
        schema = (ROOT/'schema.prisma').read_text(encoding='utf-8-sig')
        schema = schema.replace('file:./data/db/alimentia.db', 'file:' + database.as_posix())
        schema_path = work/'schema.prisma'
        schema_path.write_text(schema, encoding='utf-8')
        run_prisma('validate', '--schema', str(schema_path))
        if baseline_required:
            run_prisma('migrate', 'resolve', '--applied', BASELINE, '--schema', str(schema_path))
        run_prisma('migrate', 'deploy', '--schema', str(schema_path))
    with closing(sqlite3.connect(database)) as db:
        db.row_factory = sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Post-migration integrity check failed')
        patient_query, plan_query = preservation_queries(db)
        patients = {r['id']: dict(r) for r in db.execute(patient_query)}
        plans = {r['id']: dict(r) for r in db.execute(plan_query)}
        for previous in old_patients:
            current = patients.get(previous['id'])
            if current != previous:
                raise RuntimeError('Legacy patient preservation check failed')
        for previous in old_plans:
            current = plans.get(previous['id'])
            expected = {**previous, 'status': STATUS.get(previous['status'], previous['status'])}
            if current != expected:
                raise RuntimeError('Legacy plan preservation check failed')
    print(f'Migration verified: preserved {len(old_patients)} patients and {len(old_plans)} plans.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=pathlib.Path, default=ROOT/'data/db/alimentia.db')
    migrate(parser.parse_args().database)
