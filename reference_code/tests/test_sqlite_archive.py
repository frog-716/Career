from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from reference_code.sqlite_archive import copy_database


class SQLiteArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.sqlite3"
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("CREATE TABLE notes(id TEXT PRIMARY KEY, body TEXT)")
            db.execute("INSERT INTO notes VALUES (?, ?)", ("fictional-1", "虚构工作记录"))
            db.commit()

    def test_backup_and_restore_to_new_path_preserve_data(self):
        backup = copy_database(self.source, self.root / "backup.sqlite3")
        restored = copy_database(backup, self.root / "restore" / "workspace.sqlite3")
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute("SELECT * FROM notes").fetchall(),
                             [("fictional-1", "虚构工作记录")])
            self.assertEqual(db.execute("PRAGMA quick_check").fetchone()[0], "ok")

    def test_existing_target_and_source_are_unchanged(self):
        target = self.root / "existing.sqlite3"
        target.write_bytes(b"existing-user-file")
        original = self.source.read_bytes()
        with self.assertRaises(FileExistsError):
            copy_database(self.source, target)
        self.assertEqual(target.read_bytes(), b"existing-user-file")
        with self.assertRaises(FileExistsError):
            copy_database(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_source_does_not_create_source_or_target(self):
        missing = self.root / "absent.sqlite3"
        target = self.root / "new.sqlite3"
        with self.assertRaises(FileNotFoundError):
            copy_database(missing, target)
        self.assertFalse(missing.exists())
        self.assertFalse(target.exists())

    def test_invalid_source_does_not_leave_success_artifact(self):
        invalid = self.root / "invalid.sqlite3"
        invalid.write_bytes(b"not a database")
        target = self.root / "new.sqlite3"
        with self.assertRaises(sqlite3.DatabaseError):
            copy_database(invalid, target)
        self.assertFalse(target.exists())
        self.assertEqual(invalid.read_bytes(), b"not a database")

    def test_committed_wal_data_is_included(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA wal_autocheckpoint=0")
            db.execute("INSERT INTO notes VALUES (?, ?)", ("fictional-2", "WAL已提交"))
            db.commit()
            target = copy_database(self.source, self.root / "wal-copy.sqlite3")
            with closing(sqlite3.connect(target)) as result:
                self.assertEqual(result.execute("SELECT count(*) FROM notes").fetchone()[0], 2)

    def test_dangling_symlink_is_not_overwritten(self):
        target = self.root / "link.sqlite3"
        target.symlink_to(self.root / "not-created.sqlite3")
        with self.assertRaises(FileExistsError):
            copy_database(self.source, target)
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.root / "not-created.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
