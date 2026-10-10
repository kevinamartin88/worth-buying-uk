import json
import subprocess
from pathlib import Path


def test_regional_measurement_and_duplicate_listener_guard():
    source = (Path(__file__).resolve().parents[1] / 'automation/retailer-measurement.js').read_text()
    harness = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const source=SOURCE;
for(const [hostname,property] of [['www.worthbuyinguk.co.uk','G-KL9MHT5ZJ1'],['www.worthbuyingusa.com','G-EEYCNV01MN']]) {
 let listeners=[],calls=[];
 const context={URL,location:{hostname,pathname:'/2026/10/guide.html'},window:{gtag:(...args)=>calls.push(args)},document:{addEventListener:(name,fn)=>listeners.push(fn)}};
 vm.runInNewContext(source,context);vm.runInNewContext(source,context);
 assert.equal(listeners.length,1);
 const link={href:'https://www.ebay.co.uk/itm/123',getAttribute:()=>null,closest:()=>null};
 listeners[0]({target:{closest:()=>link}});
 assert.equal(calls.length,1);assert.equal(calls[0][1],'wb_retailer_click');assert.equal(calls[0][2].send_to,property);
 link.href='https://example.com/';listeners[0]({target:{closest:()=>link}});assert.equal(calls.length,1);
 link.href='https://ebay.com.evil.test/';listeners[0]({target:{closest:()=>link}});assert.equal(calls.length,1);
}
'''.replace('SOURCE', json.dumps(source))
    subprocess.run(['node', '-e', harness], check=True, capture_output=True, text=True)
