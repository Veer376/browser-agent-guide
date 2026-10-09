import shutil
import subprocess
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / 'scripts/pw-action-visuals.cjs'


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class ActionVisualTests(unittest.TestCase):
    def test_existing_and_new_pages_are_enabled_once_and_errors_are_nonfatal(self):
        code = '''
const assert=require('node:assert/strict');
const {prepare}=require(process.argv[1]);
(async()=>{
let listener, calls=0, warnings=0;
const page={screencast:{showActions:async options=>{calls++;assert.equal(options.cursor,'pointer');}}};
const pages=[page];
const context={pages:()=>pages,on:(name,fn)=>{assert.equal(name,'page');listener=fn;}};
const ready=await prepare(context,{emit:()=>warnings++});
await ready();assert.equal(calls,1);
const other={screencast:{showActions:async()=>{calls++;throw Error('closed');}}};
pages.push(other);listener(other);await ready();await ready();
assert.equal(calls,2);assert.equal(warnings,1);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', code, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_modular_cursor_theme_and_lifecycle_classification(self):
        code = r'''
const assert = require('node:assert/strict');
const script = require(process.argv[1]);
const path = require('node:path');
const base = path.join(path.dirname(process.argv[1]), 'visual-system');
const cursor = require(path.join(base, 'cursor.cjs'));
const theme = require(path.join(base, 'theme.cjs'));
const {CSS} = require(path.join(base, 'motion.cjs'));
const tests = {
  browser_type: 'typing',
  browser_press_key: 'typing',
  browser_mouse_wheel: 'scrolling',
  browser_snapshot: 'reading',
  browser_take_screenshot: 'screenshot',
  browser_evaluate: 'inspecting',
  browser_click: '',
  browser_hover: '',
};
for (const [name, result] of Object.entries(tests))
  assert.equal(script.classifyAction(name), result, name);
assert.match(cursor.cursorMarkup(), /pw-ink-white/);
assert.doesNotMatch(cursor.cursorMarkup(), /#181818/);
assert.equal(theme.normalizeTheme('unexpected'), 'auto');
assert.equal(theme.normalizeTheme('dark'), 'dark');
assert.match(CSS, /\.pw-agent-pill/);
assert.match(CSS, /border:2px solid var\(--pw-ink-white\)/);
assert.match(CSS, /box-shadow:none!important/);
assert.match(CSS, /prefers-reduced-motion/);
assert.match(CSS, /prefers-color-scheme: dark/);
assert.match(CSS, /pw-floating-z/);
assert.equal((CSS.match(/@keyframes pw-look-(?:left|right|up|down)/g)||[]).length, 4);
'''
        result = subprocess.run(['node', '-e', code, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
