"""Baixa e restaura assets de pesquisa, com hashes e extração segura."""
from pathlib import Path,PurePosixPath
import argparse,datetime,hashlib,json,shutil,stat,sys,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha256(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def verify_asset(path,asset):
    path=Path(path)
    if path.stat().st_size!=asset['bytes'] or sha256(path)!=asset['sha256']:
        raise ValueError(f'Tamanho/SHA-256 divergente: {path.name}. O arquivo não será restaurado.')


def restore_archive(path,root=ROOT,backup_conflicts=False):
    root=Path(root).resolve();plans=[];total=0
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    with zipfile.ZipFile(path) as archive:
        # Conferir todo o plano antes de escrever: um conflito não deixa restauração parcial.
        for item in archive.infolist():
            if item.is_dir():continue
            name=item.filename.replace('\\','/');parts=PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or ':' in name or not parts.parts or parts.parts[0] not in {'output','work','data'}:
                raise ValueError(f'Caminho recusado no ZIP: {name}')
            if stat.S_ISLNK(item.external_attr>>16):raise ValueError(f'Link simbólico recusado: {name}')
            target=(root/Path(*parts.parts)).resolve()
            if not target.is_relative_to(root):raise ValueError(f'Caminho fora do projeto: {name}')
            total+=item.file_size
            if item.file_size>512*1024*1024 or total>2*1024*1024*1024:raise ValueError('ZIP acima do limite de extração')
            payload=archive.read(item);digest=hashlib.sha256(payload).hexdigest()
            conflict=target.exists() and sha256(target)!=digest
            if conflict and not backup_conflicts:raise FileExistsError(f'Arquivo diferente já existe: {name}. Use --backup-conflicts ou outra cópia do projeto.')
            plans.append((target,payload,conflict,name))
        if len({str(p[0]) for p in plans})!=len(plans):raise ValueError('ZIP contém destinos duplicados')
        for target,payload,conflict,name in plans:
            if target.exists() and not conflict:continue
            if conflict:
                backup=root/'work'/'restore-backups'/stamp/Path(name)
                backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(payload)
    return len(plans)


def download(asset):
    folder=ROOT/'work'/'downloads';folder.mkdir(parents=True,exist_ok=True)
    path=folder/asset['name']
    if path.exists():
        try:verify_asset(path,asset);return path
        except ValueError:pass
    print(f'Baixando {asset["name"]} ({asset["bytes"]/1e6:.1f} MB)...',flush=True)
    temporary=path.with_suffix(path.suffix+'.part')
    request=urllib.request.Request(asset['url'],headers={'User-Agent':'ImpactUFSCar-Research-Data/1.0'})
    with urllib.request.urlopen(request,timeout=90) as response,temporary.open('wb') as destination:
        shutil.copyfileobj(response,destination)
    verify_asset(temporary,asset)
    temporary.replace(path)
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--list',action='store_true')
    selection.add_argument('--download-research',action='store_true')
    selection.add_argument('--download-b3',action='store_true')
    selection.add_argument('--restore',type=Path)
    parser.add_argument('--backup-conflicts',action='store_true')
    args=parser.parse_args()
    manifest=json.loads((ROOT/'data'/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    assets=manifest['assets']
    if args.list:
        for asset in assets:print(f'{asset["name"]}\t{asset["bytes"]/1e6:.1f} MB\t{asset["sha256"]}')
        return
    if args.restore:
        matches=[a for a in assets if a['name']==args.restore.name and a['destination']=='project-archive']
        if len(matches)!=1:raise ValueError('Nome de pacote não consta no manifesto publicado')
        verify_asset(args.restore,matches[0]);count=restore_archive(args.restore,backup_conflicts=args.backup_conflicts)
        print(f'Restaurados/conferidos {count} arquivos.');return
    if args.download_research:
        asset=next(a for a in assets if a['destination']=='project-archive')
        count=restore_archive(download(asset),backup_conflicts=args.backup_conflicts)
        print(f'Restaurados/conferidos {count} arquivos.');return
    for asset in assets:
        if asset['destination']=='project-archive':continue
        source=download(asset);target=ROOT/asset['destination']
        if target.exists():
            verify_asset(target,asset);continue
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    print('Fontes B3 completas conferidas e restauradas.')


if __name__=='__main__':
    try:main()
    except Exception as exc:print(f'Falha: {exc}',file=sys.stderr);raise SystemExit(1)
