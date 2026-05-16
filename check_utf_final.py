import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')

HOST='10.200.9.11'; USER='root'; PASS='nWTGzzDqwyFyNJhqMhvcjEJj'
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,port=22,username=USER,password=PASS,timeout=15,look_for_keys=False,allow_agent=False)

_,so,se=c.exec_command("""docker exec anamnezai-backend-1 python3 -c "
with open('/app/frontend/doctor.html','rb') as f: d=f.read()
txt = d.decode('utf-8')
repl = txt.count(chr(0xFFFD))
print('replacement_chars:', repl)
print('has_g_breve (U+011F):', chr(0x11F) in txt)
print('has_u_umlaut (U+00FC):', chr(0xFC) in txt)
print('has_s_cedilla (U+015F):', chr(0x15F) in txt)
print('has_dotless_i (U+0131):', chr(0x131) in txt)
print('has_red_emoji:', chr(0x1f534) in txt)
print('has_yellow_emoji:', chr(0x1f7e1) in txt)
idx=txt.find('statRedSub')
print('statRedSub hex:', txt[idx:idx+50].encode('utf-8').hex())
" """, timeout=20)
out=(so.read()+se.read()).decode('utf-8','replace')
print(out)
c.close()

