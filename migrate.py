import os
import psycopg2
from psycopg2.extras import DictCursor

# CONFIGURATION: Replace these connection strings
SOURCE_DB = "postgresql://postgres.ypzdsysivyjsdsuvzjtf:chheeMAKAUT@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"
TARGET_DB = "postgresql://postgres.hvowenqqlxkiuskurvoc:unnati_remedy@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

TABLES = [
    'subjects',
    'users',
    'students',
    'assignment_groups',
    'exams',
    'questions',
    'options',
    'assessments',
    'classifications',
    'remedial_schedules',
    'exam_allotments',
    'exam_submissions',
    'student_answers'
]

def migrate():
    if "YOUR_NEW" in TARGET_DB or not TARGET_DB:
        print("Please replace TARGET_DB with your new Supabase connection string!")
        return

    print("Connecting to source database...")
    try:
        src_conn = psycopg2.connect(SOURCE_DB)
        src_cur = src_conn.cursor(cursor_factory=DictCursor)
    except Exception as e:
        print(f"Failed to connect to source: {e}")
        return

    print("Connecting to target database...")
    try:
        tgt_conn = psycopg2.connect(TARGET_DB)
        tgt_cur = tgt_conn.cursor()
    except Exception as e:
        print(f"Failed to connect to target: {e}")
        src_conn.close()
        return

    try:
        # Disable all constraints/triggers for the session to insert without foreign key errors
        print("Disabling triggers/foreign key checks on target...")
        tgt_cur.execute("SET session_replication_role = replica;")

        for table in TABLES:
            print(f"Migrating table: {table}...")
            
            # 1. Fetch data from source
            src_cur.execute(f'SELECT * FROM "{table}";')
            rows = src_cur.fetchall()
            
            if not rows:
                print(f"  No data in {table}.")
                continue
                
            columns = list(rows[0].keys())
            col_names = ", ".join([f'"{c}"' for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            
            # 2. Clear target table (just in case)
            tgt_cur.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
            
            # 3. Insert into target
            insert_query = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders});'
            data_to_insert = [tuple(row) for row in rows]
            
            tgt_cur.executemany(insert_query, data_to_insert)
            print(f"  Successfully copied {len(rows)} rows into {table}.")

            # 4. Reset primary key sequence so future inserts do not fail with duplicate errors
            try:
                tgt_cur.execute(f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), COALESCE(MAX(id), 1)) FROM \"{table}\";")
            except Exception:
                # If table doesn't use a standard serial 'id' sequence, ignore
                pass

        # Commit target changes
        tgt_conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        tgt_conn.rollback()
        print(f"\nMigration failed: {e}")
    finally:
        src_conn.close()
        tgt_conn.close()

if __name__ == "__main__":
    migrate()
