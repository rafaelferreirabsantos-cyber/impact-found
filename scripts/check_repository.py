"""Verifica arquivos versionáveis, links locais, JSONs, tamanhos e segredos comuns."""
from pathlib import Path
import json,re,subprocess,sys

ROOT=Path(__file__).resolve().parents[1]
SECRET_PATTERNS=[re.compile(r'gh[pousr]_[A-Za-z0-9]{25,}'),
                 re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
                 re.compile(r'AKIA[0-9A-Z]{16}'),
                 re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
                 re.compile(r'(?im)^\s*BRAPI_TOKEN\s*=\s*["\x27]?[A-Za-z0-9_-]{15,}')]


def versionable_files():
    result=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,check=True)
    return sorted({ROOT/name for name in result.stdout.decode('utf-8').split('\0') if name and (ROOT/name).is_file()})


def check():
    errors=[];files=versionable_files()
    for file in files:
        rel=file.relative_to(ROOT).as_posix()
        if file.stat().st_size>12*1024*1024:errors.append(f'Arquivo grande no Git: {rel}; use Release')
        if file.name in {'.env','credentials.json','token.json'} or file.suffix in {'.pem','.key'}:errors.append(f'Arquivo sensível: {rel}')
        try:text=file.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:continue
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):errors.append(f'Possível segredo em {rel} (conteúdo não exibido)')
        if file.suffix in {'.json','.ipynb'}:
            try:json.loads(text)
            except json.JSONDecodeError:errors.append(f'JSON inválido: {rel}')
        if file.suffix.lower()=='.md':
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
                link=link.strip('<>').split('#',1)[0]
                if not link or re.match(r'[A-Za-z][A-Za-z0-9+.-]*:',link):continue
                target=(file.parent/link).resolve()
                if not target.exists():errors.append(f'Link local ausente: {rel} -> {link}')
    if errors:
        print('\n'.join(errors));return 1
    print(f'PASS: {len(files)} arquivos; links locais, JSONs, tamanho e padrões de segredos conferidos.')
    return 0


if __name__=='__main__':raise SystemExit(check())
