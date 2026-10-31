"""OS-specific locations and conservative CPU defaults, shared by both desktops."""
from pathlib import Path
import os,platform

ROOT=Path(__file__).resolve().parent

def data_dir():
    custom=os.environ.get('IPDF_DATA_DIR')
    if custom:return Path(custom).expanduser()
    if platform.system()=='Windows':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'ReGlyphPDF'
    if platform.system()=='Darwin':return Path.home()/'Library/Application Support/ReGlyphPDF'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'ReGlyphPDF'

def cache_dir():return data_dir()/'cache'

def model_dir():
    if os.environ.get('IPDF_MODEL_DIR'):return Path(os.environ['IPDF_MODEL_DIR']).expanduser()
    return ROOT/'model' if (ROOT/'model').is_dir() else data_dir()/'model'

def configure_environment():
    # Setting actual library thread controls precedes imports of numerical runtimes.
    try:value=int(os.environ.get('IPDF_CPU_THREADS','2'))
    except ValueError:value=2
    threads=str(max(1,min(4,value)))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]=threads
    os.environ.update(QT_API='pyside6',PYTHONDONTWRITEBYTECODE='1',PADDLE_PDX_CACHE_HOME=str(model_dir()),
        PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',FLAGS_use_mkldnn='0',FLAGS_use_onednn='0')
    return int(threads)

def ui_font():return 'Microsoft YaHei UI' if platform.system()=='Windows' else 'PingFang SC' if platform.system()=='Darwin' else 'Noto Sans'


def initialize_data():
    import json,shutil
    folder=data_dir();folder.mkdir(parents=True,exist_ok=True)
    settings=folder/'settings.json'
    if not settings.exists():
        source=ROOT/'settings.json'
        data=json.loads(source.read_text(encoding='utf-8')) if source.exists() else {'ui_lang':'zh'}
        # Legacy bundled model path becomes a portable absolute runtime choice.
        if data.get('ocr_paddlex_home')=='model':data['ocr_paddlex_home']=''
        if data.get('inpaint_api_url')=='http://127.0.0.1:8080/api/v1/inpaint':data['inpaint_api_url']='http://127.0.0.1:18181/api/v1/inpaint'
        settings.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    legacy=ROOT/'自动备份/最近工程.ipdfedit'
    target=folder/'自动备份/最近工程.ipdfedit'
    if legacy.exists() and not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(legacy,target)
    return folder
