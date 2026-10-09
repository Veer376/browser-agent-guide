import shutil
import subprocess
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts/pw-browser-compatibility.cjs'

@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class BrowserCompatibilityTests(unittest.TestCase):
    def test_marker_waits_for_document_root_without_rewriting_page_content(self):
        code = '''
const assert=require('node:assert/strict');
const {markAutomationPage}=require(process.argv[1]);
let attributes={},callback,disconnected=false;
global.document={documentElement:null};
global.MutationObserver=class {constructor(cb){callback=cb;}observe(){}disconnect(){disconnected=true;}};
markAutomationPage();
assert.deepEqual(attributes,{});
document.documentElement={setAttribute:(k,v)=>attributes[k]=v};
callback();assert.equal(attributes['data-pw-browser-automation'],'1');assert.equal(disconnected,true);
'''
        result = subprocess.run(['node', '-e', code, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
