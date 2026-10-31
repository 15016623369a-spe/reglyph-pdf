"""Install two isolated Python 3.11 environments on macOS or Windows x64."""
from pathlib import Path
import argparse,os,platform,subprocess,sys,venv
ROOT=Path(__file__).resolve().parent

def check_host():
    if sys.version_info[:2]!=(3,11):raise RuntimeError('ReGlyph PDF 使用 Python 3.11。请用 Python 3.11 运行安装程序。')
    if platform.system() not in ('Darwin','Windows'):raise RuntimeError('支持 macOS 与 Windows 桌面。')
    if platform.system()=='Windows' and platform.machine().lower() not in ('amd64','x86_64'):raise RuntimeError('Windows 请使用 x64 版 Python 3.11。')

def install(name,requirements,*,check_only=False):
    folder=ROOT/name;python=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    command=[str(python),'-m','pip','install','-r',str(ROOT/requirements)]
    if check_only:
        command=[sys.executable,'-m','pip','install','--dry-run','--ignore-installed','-r',str(ROOT/requirements)]
    else:
        if not python.exists():venv.EnvBuilder(with_pip=True).create(folder)
        subprocess.check_call([str(python),'-m','pip','install','--upgrade','pip'])
    subprocess.check_call(command)
    if not check_only:subprocess.check_call([str(python),'-m','pip','check'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--editor-only',action='store_true');parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    try:
        check_host();install('.venv-editor','requirements-editor.txt',check_only=args.dry_run)
        if not args.editor_only:install('.venv-inpaint','requirements-repair.txt',check_only=args.dry_run)
        print('安装检查完成。首次打开时会准备识别和修复模型，需要联网。' if not args.dry_run else '依赖解析检查完成；未执行安装。')
        return 0
    except (RuntimeError,subprocess.CalledProcessError) as e:print(f'安装未完成：{e}',file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
