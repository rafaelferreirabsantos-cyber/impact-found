"""Empacota dados e painel de validação no template, sem alterar seu layout base."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]


def render_dashboard(backtest_path,output_path,validation_path=None):
    template=(ROOT/'dashboard'/'index.html').read_text(encoding='utf-8')
    def safe_json(path):
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        return json.dumps(value,ensure_ascii=False,allow_nan=False).replace('</script','<\\/script')
    markers={'/*__EMBEDDED_IMPACT_DATA__*/null':safe_json(backtest_path),
             '/*__EMBEDDED_VALIDATION_DATA__*/null':safe_json(validation_path) if validation_path else 'null',
             '<!--__VALIDATION_SECTION__-->':(ROOT/'dashboard'/'validation-panel.html').read_text(encoding='utf-8'),
             '/*__VALIDATION_SCRIPT__*/':(ROOT/'dashboard'/'validation-panel.js').read_text(encoding='utf-8')}
    for marker,value in markers.items():
        if template.count(marker)!=1:raise ValueError(f'Marcador não único no template: {marker}')
        template=template.replace(marker,value,1)
    Path(output_path).write_text(template,encoding='utf-8')
    return Path(output_path)
