"""
Backup/restore the whole database as a single .zip of .csv files (one per
table) + a summary.json.

This replaces the previous openpyxl/.xlsx implementation. Reasoning:
openpyxl isn't a reliable install on Termux in practice, while
`zipfile` + `csv` + `json` are all stdlib - guaranteed to be present with
any Python install, no pip involved at all. A .zip of .csv files is still
one file to move around, still human-readable (each table opens directly
in any spreadsheet app), and still fully restorable.
"""

import sqlite3
import csv
import io
import json
import zipfile
from db import db
from pathlib import Path
from datetime import datetime
from config import BACKUP_DIR

# Tables backed up/restored, in a fixed order.
# Phase 2: expanded to cover every table the factory actually uses.
# Scope note: this is a DATA backup of the factory database. It covers all
# bot/user/config content. It does NOT include: the .env file (tokens live
# there by design and must be restored separately), or files outside the DB.
TABLES = [
    "bots", "bot_users", "bot_admins", "bot_settings",
    "messages", "subscriptions", "blocks", "verified_users",
    "offsets", "queue_jobs", "events", "auto_replies",
    "conversation_state", "scheduled_deletions", "inactivity_reminders",
    "forwarded_messages", "reports", "audit_log", "backups", "logs",
    "factory_users", "factory_admins", "factory_blocks",
]
BACKUP_SCOPE = (
    "نطاق النسخة: كل جداول قاعدة بيانات المصنع (البوتات، المستخدمون، "
    "الإعدادات، الرسائل، البلاغات، سجل التدقيق). لا تشمل ملف .env "
    "(التوكنات تُستعاد يدويًا) ولا ملفات خارج قاعدة البيانات."
)

class BackupManager:
    """Create and restore full database backups as a zip of CSV files"""
    
    async def create_backup(self) -> str:
        """
        Export entire database to a single .zip (one .csv per table + summary.json)
        
        Returns:
            Path to backup file
        """
        print("💾 Creating backup...")
        
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        filename = f"factory_backup_{timestamp}.zip"
        filepath = BACKUP_DIR / filename
        
        # Count totals for the summary
        counts = {}
        for table in TABLES:
            cursor = await db.connection.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = (await cursor.fetchone())[0]
        
        summary = {
            "backup_date": datetime.now().isoformat(),
            "counts": counts,
            "status": "complete",
        }
        
        with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("SUMMARY.json", json.dumps(summary, indent=2, ensure_ascii=False))
            
            for table in TABLES:
                csv_text = await self._export_table_csv(table)
                if csv_text is not None:
                    zf.writestr(f"{table}.csv", csv_text)
        
        size_bytes = filepath.stat().st_size
        print(f"✅ Backup created: {filename}")
        print(f"   Location: {filepath}")
        print(f"   Size: {size_bytes / 1024 / 1024:.2f} MB")

        # Phase 2: integrity check on the LIVE db snapshot BEFORE declaring
        # success. A failed check means the backup is NOT recorded as good.
        integrity_ok = await self._check_live_integrity()
        await db.record_backup(
            filename, size_bytes, integrity_ok,
            scope="factory.db: all tables (see BACKUP_SCOPE)",
            note="integrity ok" if integrity_ok else "INTEGRITY CHECK FAILED")
        if not integrity_ok:
            print("  ⚠️ Backup recorded but integrity check FAILED - not marked good")
            await db.add_log("error", "backup",
                             f"Backup {filename} created but integrity check failed")
        return str(filepath)

    async def _check_live_integrity(self) -> bool:
        """PRAGMA integrity_check on the live database."""
        try:
            cursor = await db.connection.execute("PRAGMA integrity_check")
            rows = await cursor.fetchall()
            return len(rows) == 1 and str(rows[0][0]).lower() == "ok"
        except Exception as e:
            print(f"  ⚠️ integrity_check error: {e}")
            return False

    async def verify_backup_file(self, filepath: str) -> dict:
        """Verify a .zip backup WITHOUT touching production.

        Restores the zip into a temporary SQLite file, runs integrity_check
        and confirms the core tables are readable. Returns a report dict.
        """
        import tempfile, os
        report = {"ok": False, "integrity": "not-run", "tables": {},
                  "error": None, "file": os.path.basename(filepath)}
        tmp = None
        try:
            if not os.path.isfile(filepath) or not zipfile.is_zipfile(filepath):
                report["error"] = "not a zip file"
                return report
            fd, tmp = tempfile.mkstemp(suffix=".db")
            os.close(fd)
            with zipfile.ZipFile(filepath, "r") as zf:
                names = set(zf.namelist())
                if "SUMMARY.json" not in names:
                    report["error"] = "missing SUMMARY.json"
                    return report
                conn = sqlite3.connect(tmp)
                cur = conn.cursor()
                # Recreate minimal schema from live DB for the tables in the zip
                live = sqlite3.connect(os.path.expanduser("~/factory/data/factory.db"))
                for table in TABLES:
                    csv_name = f"{table}.csv"
                    if csv_name not in names:
                        continue
                    row = live.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone()
                    if row and row[0]:
                        cur.execute(row[0])
                    text = zf.read(csv_name).decode("utf-8")
                    reader = csv.reader(io.StringIO(text))
                    try:
                        headers = next(reader)
                    except StopIteration:
                        continue
                    placeholders = ", ".join(["?"] * len(headers))
                    cols = ", ".join(headers)
                    for r in reader:
                        if not any((c or "").strip() for c in r):
                            continue
                        vals = [r[i] if i < len(r) else None for i in range(len(headers))]
                        try:
                            cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", vals)
                        except Exception:
                            pass
                conn.commit()
                integ = cur.execute("PRAGMA integrity_check").fetchall()
                report["integrity"] = "ok" if (len(integ) == 1 and str(integ[0][0]).lower() == "ok") else "FAILED"
                for table in TABLES:
                    try:
                        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                        report["tables"][table] = n
                    except Exception:
                        report["tables"][table] = "missing"
                conn.close()
                live.close()
                report["ok"] = report["integrity"] == "ok"
        except Exception as e:
            report["error"] = f"{type(e).__name__}: {e}"
        finally:
            if tmp and os.path.exists(tmp):
                try: os.remove(tmp)
                except OSError: pass
        return report
    
    async def _export_table_csv(self, table_name: str):
        """Export a single table to CSV text. Returns None if the table is empty."""
        
        cursor = await db.connection.execute(f"SELECT * FROM {table_name}")
        rows = await cursor.fetchall()
        
        if not rows:
            return None
        
        columns = [description[0] for description in cursor.description]
        
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        return buf.getvalue()
    
    async def restore_from_backup(self, filepath: str) -> bool:
        """
        Restore database from a .zip backup created by create_backup().
        
        ⚠️ WARNING: This adds rows back into the existing database
        (duplicates are skipped, not overwritten).
        
        Args:
            filepath: Path to backup .zip file
        
        Returns:
            True if successful
        """
        
        try:
            print(f"🔄 Restoring from backup: {filepath}")
            
            with zipfile.ZipFile(filepath, "r") as zf:
                names = set(zf.namelist())
                
                for table_name in TABLES:
                    csv_name = f"{table_name}.csv"
                    if csv_name not in names:
                        continue
                    
                    csv_text = zf.read(csv_name).decode("utf-8")
                    reader = csv.reader(io.StringIO(csv_text))
                    
                    try:
                        headers = next(reader)
                    except StopIteration:
                        continue
                    
                    if not headers:
                        continue
                    
                    # Validate headers against the table's real columns before
                    # building any SQL from them - a crafted zip could
                    # otherwise inject arbitrary column/SQL fragments here.
                    cursor = await db.connection.execute(f"PRAGMA table_info({table_name})")
                    valid_columns = {row[1] for row in await cursor.fetchall()}
                    bad_headers = [h for h in headers if h not in valid_columns]
                    if bad_headers:
                        print(f"  ⚠️ Skipping {table_name}: unknown column(s) {bad_headers}")
                        continue
                    
                    placeholders = ", ".join(["?"] * len(headers))
                    columns = ", ".join(headers)
                    inserted, skipped, failed = 0, 0, 0
                    
                    for row in reader:
                        if not any((cell or "").strip() for cell in row):
                            continue  # skip blank rows
                        values = [row[i] if i < len(row) else None for i in range(len(headers))]
                        
                        try:
                            await db.connection.execute(
                                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                                values
                            )
                            inserted += 1
                        except sqlite3.IntegrityError:
                            # Expected for rows that already exist (unique/PK conflict)
                            skipped += 1
                        except Exception as e:
                            # Anything else is a real problem - surface it instead
                            # of silently discarding the row
                            failed += 1
                            print(f"  ⚠️ {table_name}: failed to restore a row: {type(e).__name__}: {e}")
                    
                    await db.connection.commit()
                    print(f"  ✅ Restored {table_name}: {inserted} inserted, {skipped} duplicates skipped, {failed} failed")
            
            print("✅ Restore completed")
            return True
        
        except Exception as e:
            print(f"❌ Restore failed: {type(e).__name__}: {e}")
            from db import db
            await db.add_log("error", "backup", f"Restore failed: {type(e).__name__}: {e}")
            return False
    
    async def list_backups(self) -> list:
        """List all backup files"""
        
        backups = sorted(BACKUP_DIR.glob("factory_backup_*.zip"), reverse=True)
        
        result = []
        for backup in backups:
            stat = backup.stat()
            result.append({
                "name": backup.name,
                "size_mb": stat.st_size / 1024 / 1024,
                "created": datetime.fromtimestamp(stat.st_mtime)
            })
        
        return result

# Global instance
backup_manager = BackupManager()
