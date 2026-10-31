import os,sys,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'app' if (BASE/'app').exists() else BASE.parent))
import platform_config as config

class PlatformTests(unittest.TestCase):
 def test_per_user_settings_windows(self):
  with patch.dict(os.environ,{'LOCALAPPDATA':'C:/Users/Example/AppData/Local'},clear=True),patch.object(config.platform,'system',return_value='Windows'):
   self.assertEqual(str(config.data_dir()).replace('\\','/'),'C:/Users/Example/AppData/Local/ReGlyphPDF')
   self.assertEqual(config.ui_font(),'Microsoft YaHei UI')
 def test_per_user_settings_mac(self):
  with patch.dict(os.environ,{},clear=True),patch.object(config.platform,'system',return_value='Darwin'):
   self.assertTrue(str(config.data_dir()).endswith('Library/Application Support/ReGlyphPDF'))
   self.assertEqual(config.ui_font(),'PingFang SC')
 def test_thread_limits_apply_to_all_numeric_libraries(self):
  for requested,expected in [('2',2),('999',4),('0',1),('bad',2)]:
   with patch.dict(os.environ,{'IPDF_CPU_THREADS':requested},clear=True):
    self.assertEqual(config.configure_environment(),expected)
    for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS']:
     self.assertEqual(os.environ[key],str(expected))
 def test_migration_keeps_existing_user_settings_and_backups(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)/'source';root.mkdir();data=Path(folder)/'data'
   (root/'settings.json').write_text(json.dumps(dict(ui_lang='zh',ocr_paddlex_home='model',inpaint_api_url='http://127.0.0.1:8080/api/v1/inpaint')))
   (root/'自动备份').mkdir();(root/'自动备份/最近工程.ipdfedit').write_bytes(b'existing backup')
   with patch.dict(os.environ,{'IPDF_DATA_DIR':str(data)},clear=True),patch.object(config,'ROOT',root):
    config.initialize_data();settings=json.loads((data/'settings.json').read_text())
    self.assertEqual(settings['inpaint_api_url'],'http://127.0.0.1:18181/api/v1/inpaint');self.assertEqual(settings['ocr_paddlex_home'],'')
    self.assertEqual((data/'自动备份/最近工程.ipdfedit').read_bytes(),b'existing backup')
    (data/'settings.json').write_text('{"custom":true}');config.initialize_data();self.assertTrue(json.loads((data/'settings.json').read_text())['custom'])
 def test_explicit_model_directory(self):
  with patch.dict(os.environ,{'IPDF_MODEL_DIR':str(BASE/'model-fixture')},clear=True):self.assertEqual(config.model_dir(),BASE/'model-fixture')

if __name__=='__main__':unittest.main(verbosity=2)
