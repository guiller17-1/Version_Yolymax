const now=()=>Math.floor(Date.now()/1000), uid=()=>crypto.randomUUID(), enc=new TextEncoder();
const hex=b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,'0')).join('');
const random=n=>hex(crypto.getRandomValues(new Uint8Array(n)));
const digest=async s=>hex(await crypto.subtle.digest('SHA-256',enc.encode(s)));
function err(message,status=400){throw Object.assign(Error(message),{status})}
function equal(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let v=0;for(let i=0;i<a.length;i++)v|=a.charCodeAt(i)^b.charCodeAt(i);return v===0}
function email(v){if(typeof v!=='string'||v.length>254||!/^\S+@[^\s@]+\.[^\s@]+$/.test(v.trim()))err('Ingresa un correo válido.');return v.trim().toLowerCase()}
function name(v){if(typeof v!=='string'||!v.trim()||v.length>100)err('Ingresa un nombre válido.');return v.trim()}
function password(v){if(typeof v!=='string'||v.length<14||v.length>200)err('Usa una contraseña de 14 a 200 caracteres.');return v}
async function hash(p,s){const key=await crypto.subtle.importKey('raw',enc.encode(p),'PBKDF2',false,['deriveBits']);return hex(await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:enc.encode(s),iterations:100000},key,256))}
async function credentials(p){const salt=random(24);return {salt,hash:await hash(password(p),salt)}}
async function verify(u,p){if(typeof p!=='string'||p.length>200)return false;const h=await hash(p,u?.salt||'000000000000000000000000000000000000000000000000');return !!u&&equal(h,u.password_hash)}
const safe=u=>({id:u.id,email:u.email,name:u.name,role:u.role,active:!!u.active});
const q=(env,sql,...args)=>env.DB.prepare(sql).bind(...args);
async function userByEmail(env,e){return q(env,'SELECT * FROM admin_users WHERE email=?',e).first()}
function token(req){return (req.headers.get('Cookie')||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-yoly='))?.slice(12)||''}
export async function currentUser(req,env){const t=token(req);if(!/^[a-f0-9]{64}$/.test(t))return null;return (await q(env,'SELECT u.* FROM admin_sessions s JOIN admin_users u ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',await digest(t),now()).first())||null}
const cookie=(t,age)=>`__Host-yoly=${t}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=${age}`;
async function newSession(env,u,json){const t=random(32);await env.DB.batch([q(env,'DELETE FROM admin_sessions WHERE expires<=?',now()),q(env,'INSERT INTO admin_sessions(token,user_id,expires) VALUES(?,?,?)',await digest(t),u.id,now()+43200)]);return json({ok:true,user:safe(u)},200,{'Set-Cookie':cookie(t,43200)})}
async function recovery(req,env,b,limit){await limit(req,env,'owner-recovery',5,900);if(typeof env.ADMIN_RECOVERY_KEY!=='string'||env.ADMIN_RECOVERY_KEY.length<32)err('El propietario debe configurar ADMIN_RECOVERY_KEY en Cloudflare.',503);if(typeof b.key!=='string'||b.key.length>300||!equal(await digest(b.key),await digest(env.ADMIN_RECOVERY_KEY)))err('Datos de recuperación incorrectos.',401)}
export async function authRoute(req,env,path,{json,readBody,limit}){
 const m=req.method;
 if(path==='/api/auth/status'&&m==='GET'){const row=await q(env,'SELECT COUNT(*) AS n FROM admin_users').first();return json({setup:row.n===0})}
 if(path==='/api/auth/setup'&&m==='POST'){const b=await readBody(req,4000);await recovery(req,env,b,limit);const row=await q(env,'SELECT COUNT(*) AS n FROM admin_users').first();if(row.n)err('El propietario ya fue creado.',409);const e=email(b.email),n=name(b.name),c=await credentials(b.password),id=uid();try{await q(env,'INSERT INTO admin_users(id,email,name,role,password_hash,salt,active,created_at) VALUES(?,?,?,?,?,?,1,?)',id,e,n,'owner',c.hash,c.salt,now()).run()}catch{err('No se pudo crear el propietario. Verifica si ya existe.',409)}return json({ok:true},201)}
 if(path==='/api/login'&&m==='POST'){await limit(req,env,'login',8,900);const b=await readBody(req,4000);const e=email(b.email);const u=await userByEmail(env,e);if(!await verify(u,b.password)||!u.active)err('Correo o contraseña incorrectos.',401);return newSession(env,u,json)}
 if(path==='/api/auth/recover'&&m==='POST'){const b=await readBody(req,4000);await recovery(req,env,b,limit);const u=await userByEmail(env,email(b.email));if(!u||u.role!=='owner'||!u.active)err('Datos de recuperación incorrectos.',401);const c=await credentials(b.password);await env.DB.batch([q(env,'UPDATE admin_users SET password_hash=?,salt=? WHERE id=?',c.hash,c.salt,u.id),q(env,'DELETE FROM admin_sessions WHERE user_id=?',u.id)]);return json({ok:true},200,{'Set-Cookie':cookie('',0)})}
 if(path==='/api/logout'&&m==='POST'){const t=token(req);if(t)await q(env,'DELETE FROM admin_sessions WHERE token=?',await digest(t)).run();return json({ok:true},200,{'Set-Cookie':cookie('',0)})}
 if(!path.startsWith('/api/auth/'))return null;
 const u=await currentUser(req,env);if(!u)err('Inicia sesión como administrador.',401);
 if(path==='/api/auth/me'&&m==='GET')return json({user:safe(u)});
 if(path==='/api/auth/password'&&m==='POST'){await limit(req,env,'change-password',8,900);const b=await readBody(req,4000);if(!await verify(u,b.current))err('La contraseña actual es incorrecta.',401);const c=await credentials(b.password);await env.DB.batch([q(env,'UPDATE admin_users SET password_hash=?,salt=? WHERE id=?',c.hash,c.salt,u.id),q(env,'DELETE FROM admin_sessions WHERE user_id=?',u.id)]);return json({ok:true},200,{'Set-Cookie':cookie('',0)})}
 if(u.role!=='owner')err('Solo el propietario puede administrar usuarios.',403);
 if(path==='/api/auth/users'&&m==='GET'){const r=await q(env,'SELECT id,email,name,role,active FROM admin_users ORDER BY created_at').all();return json({users:r.results.map(safe)})}
 if(path==='/api/auth/users'&&m==='POST'){const b=await readBody(req,4000);const e=email(b.email),n=name(b.name),c=await credentials(b.password);if(await userByEmail(env,e))err('Ese correo ya está registrado.',409);try{await q(env,'INSERT INTO admin_users(id,email,name,role,password_hash,salt,active,created_at) VALUES(?,?,?,?,?,?,1,?)',uid(),e,n,'admin',c.hash,c.salt,now()).run()}catch{err('No se pudo crear la cuenta. Comprueba que el correo no exista.',409)}return json({ok:true},201)}
 if(path==='/api/auth/users/reset'&&m==='POST'){const b=await readBody(req,4000),v=await q(env,'SELECT * FROM admin_users WHERE id=?',String(b.id||'')).first();if(!v||v.role!=='admin')err('Usuario no encontrado.',404);const c=await credentials(b.password);await env.DB.batch([q(env,'UPDATE admin_users SET password_hash=?,salt=? WHERE id=?',c.hash,c.salt,v.id),q(env,'DELETE FROM admin_sessions WHERE user_id=?',v.id)]);return json({ok:true})}
 if(path==='/api/auth/users/active'&&m==='POST'){const b=await readBody(req,4000),v=await q(env,'SELECT * FROM admin_users WHERE id=?',String(b.id||'')).first();if(!v||v.role!=='admin'||typeof b.active!=='boolean')err('Usuario no válido.');await env.DB.batch([q(env,'UPDATE admin_users SET active=? WHERE id=?',b.active?1:0,v.id),q(env,'DELETE FROM admin_sessions WHERE user_id=?',v.id)]);return json({ok:true})}
 err('Ruta no disponible.',404);
}
