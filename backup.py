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

# Tables backed up/restored, in a fixed order
TABLES = [
    "bots", "bot_users", "messages", "subscriptions", "blocks",
    "offsets", "queue_jobs", "events", "auto_replies",
]

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
        
        print(f"✅ Backup created: {filename}")
        print(f"   Location: {filepath}")
        print(f"   Size: {filepath.stat().st_size / 1024 / 1024:.2f} MB")
        
        return str(filepath)
    
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
