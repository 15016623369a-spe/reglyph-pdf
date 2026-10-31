"""Portable desktop launcher; only manages processes it starts itself."""
from pathlib import Path
import json,os,subprocess,sys,time,socket
from urllib.request import build_opener,ProxyHandler
from platform_config import ROOT,data_dir,model_dir,configure_environment,initialize_data
PORT=18181

def python_in(folder):return folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')

def runtime(kind):
    override=os.environ.get('IPDF_EDITOR_PYTHON' if kind=='editor' else 'IPDF_REPAIR_PYTHON')
    if override:return Path(override)
    names=['.venv-editor','.venv-macos'] if kind=='editor' else ['.venv-inpaint']
    for name in names:
        p=python_in(ROOT/name)
        if p.exists():return p
    return python_in(ROOT/names[0])

def service_ready(port=PORT):
    try:
        with build_opener(ProxyHandler({})).open(f'http://127.0.0.1:{port}/api/v1/model',timeout=.5) as r:return json.load(r).get('name')=='lama'
    except Exception:return False

def environment():
    threads=configure_environment();initialize_data()
    env=os.environ.copy();base=model_dir()/'iopaint'
    env.update(IPDF_CPU_THREADS=str(threads),HF_HOME=str(base/'huggingface'),TORCH_HOME=str(base/'torch'),MPLCONFIGDIR=str(data_dir()/'matplotlib'))
    return env

def main():
    env=environment();logs=data_dir()/'日志';logs.mkdir(parents=True,exist_ok=True)
    python=runtime('editor');repair_python=runtime('repair')
    if not python.exists():
        print('首次使用请先运行「首次安装」；请勿从其他电脑复制虚拟环境。',flush=True);return 1
    service=None;check='--check' in sys.argv
    try:
        if not service_ready() and repair_python.exists():
            try:
                with socket.socket() as probe:probe.bind(('127.0.0.1',PORT))
            except OSError:print('本地修复端口被其他程序占用，请关闭冲突程序或在擦字设置中填写自己的服务地址。',flush=True)
            else:
                script='import os,torch;torch.set_num_threads(int(os.environ["IPDF_CPU_THREADS"]));torch.set_num_interop_threads(1);from iopaint import entry_point;entry_point()'
                with (logs/'画面修复.log').open('a',encoding='utf-8') as log:
                    service=subprocess.Popen([str(repair_python),'-c',script,'start','--model=lama','--device=cpu','--host=127.0.0.1',f'--port={PORT}',f'--model-dir={model_dir()/"iopaint"}'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,**({'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}))
        if check:
            deadline=time.monotonic()+100
            while not service_ready() and time.monotonic()<deadline:
                if service is not None and service.poll() is not None:break
                if not repair_python.exists():break
                time.sleep(.3)
            if not service_ready():print(f'画面修复服务未就绪，请检查 {logs}。编辑和导出可独立使用。',flush=True);return 1
            test=subprocess.run([str(python),'-c','import PySide6,cv2,numpy,pptx,pymupdf;print("编辑、导出依赖与本地修复服务检查通过")'],env=env,cwd=ROOT)
            return test.returncode
        print('正在打开图片pdf文字编辑器。首次使用的模型下载可能需要联网，请耐心等待。',flush=True)
        with (logs/'编辑器.log').open('a',encoding='utf-8') as log:
            return subprocess.call([str(python),str(ROOT/'editor.py')]+sys.argv[1:],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    except KeyboardInterrupt:return 130
    finally:
        if service is not None and service.poll() is None:
            service.terminate()
            try:service.wait(timeout=10)
            except subprocess.TimeoutExpired:service.kill();service.wait()

if __name__=='__main__':sys.exit(main())
