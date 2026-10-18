/* Global Codex bridge: private key is read at runtime and is not stored in Codex configuration. */
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const blockPath=path.join(__dirname,'access-status.json');
if(fs.existsSync(blockPath)){const status=JSON.parse(fs.readFileSync(blockPath,'utf8'));if(status.blocked){process.stderr.write(String(status.error)+'\n');process.exit(1);}}
const key=(process.env.TRADER_DEV_API_KEY||fs.readFileSync(path.join(__dirname,'api-key'),'utf8')).trim();
if(!key){process.stderr.write('Brak klucza trader.dev. Uruchom configure_mcp.py.\n');process.exit(1);}
const authDir=path.join(__dirname,'auth');fs.mkdirSync(authDir,{recursive:true,mode:0o700});
const endpoint='https://mcp.trader.dev/mcp?key='+encodeURIComponent(key);
const child=spawn('npx',['-y','mcp-remote@0.15.1',endpoint,'--enable-proxy'],{stdio:['inherit','pipe','pipe'],env:{...process.env,MCP_REMOTE_CONFIG_DIR:authDir,npm_config_cache:path.join(__dirname,'npm-cache')}});
function forward(stream,target){let buffer='';const clean=s=>s.split(key).join('[REDACTED]').split(encodeURIComponent(key)).join('[REDACTED]').replace(/([?&]key=)[^&\s"'<>]+/g,'$1[REDACTED]');stream.setEncoding('utf8');stream.on('data',chunk=>{buffer+=chunk;let pos;while((pos=buffer.indexOf('\n'))>=0){target.write(clean(buffer.slice(0,pos+1)));buffer=buffer.slice(pos+1);}if(buffer.length>2e6){buffer='';target.write('Oversized MCP output omitted.\n');}});stream.on('end',()=>{if(buffer)target.write(clean(buffer));});}
forward(child.stdout,process.stdout);forward(child.stderr,process.stderr);
child.on('error',()=>{process.stderr.write('Nie uruchomiono npx/mcp-remote. Sprawdź instalację Node.js.\n');process.exitCode=1;});
child.on('exit',code=>process.exitCode=code??1);
for(const sig of ['SIGINT','SIGTERM'])process.on(sig,()=>child.kill(sig));
