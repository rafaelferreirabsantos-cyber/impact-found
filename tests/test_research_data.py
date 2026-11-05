"""Testes de restauração; arquivos temporários sem dados financeiros."""
from pathlib import Path
import hashlib,json,stat,tempfile,unittest,zipfile,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.research_data import restore_archive,verify_asset


class ResearchDataTest(unittest.TestCase):
    def make_zip(self,folder,name,payload=b'example'):
        path=Path(folder)/'fixture.zip'
        with zipfile.ZipFile(path,'w') as archive:archive.writestr(name,payload)
        return path

    def test_restore_valid_relative_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.make_zip(folder,'output/example.txt');root=Path(folder)/'repo'
            self.assertEqual(restore_archive(path,root),1)
            self.assertEqual((root/'output/example.txt').read_bytes(),b'example')

    def test_reject_path_traversal_and_unexpected_roots(self):
        for name in ['../outside.txt','/outside.txt','C:/outside.txt','src/engine.py','output/../../outside.txt']:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):restore_archive(self.make_zip(folder,name),Path(folder)/'repo')

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.zip';item=zipfile.ZipInfo('output/link');item.create_system=3;item.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(path,'w') as archive:archive.writestr(item,'../../outside')
            with self.assertRaises(ValueError):restore_archive(path,Path(folder)/'repo')

    def test_conflict_does_not_overwrite_and_backup_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.make_zip(folder,'output/example.txt');root=Path(folder)/'repo';target=root/'output/example.txt';target.parent.mkdir(parents=True);target.write_bytes(b'local')
            with self.assertRaises(FileExistsError):restore_archive(path,root)
            self.assertEqual(target.read_bytes(),b'local')
            restore_archive(path,root,True)
            backups=list((root/'work/restore-backups').rglob('example.txt'))
            self.assertEqual(len(backups),1);self.assertEqual(backups[0].read_bytes(),b'local')
            self.assertEqual(target.read_bytes(),b'example')

    def test_reject_mismatched_asset_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            path=self.make_zip(folder,'output/example.txt')
            with self.assertRaises(ValueError):verify_asset(path,{'bytes':path.stat().st_size,'sha256':'0'*64})


if __name__=='__main__':unittest.main()
