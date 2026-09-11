const modal=document.getElementById('signinModal');
let authMode='login';
const open=()=>{modal.classList.add('open');modal.setAttribute('aria-hidden','false');setTimeout(()=>document.getElementById('userEmail')?.focus(),50)};
const close=()=>{modal.classList.remove('open');modal.setAttribute('aria-hidden','true')};
document.querySelectorAll('[data-open-signin]').forEach(b=>b.addEventListener('click',open));
document.querySelectorAll('[data-close-signin]').forEach(b=>b.addEventListener('click',close));
document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
function setMode(mode){
  authMode=mode;
  document.querySelectorAll('.auth-tab').forEach(t=>t.classList.toggle('active',t.dataset.mode===mode));
  const name=document.getElementById('userName');
  const nameField=document.getElementById('nameField');
  const submit=document.getElementById('authSubmit');
  const pass=document.getElementById('userPassword');
  name.required=mode==='register';
  nameField.style.display=mode==='register'?'block':'none';
  pass.autocomplete=mode==='register'?'new-password':'current-password';
  submit.innerHTML=mode==='register'?'Create free account <span>→</span>':'Sign in to DataKite <span>→</span>';
  document.getElementById('authNote').textContent=mode==='register'?'Free account. Your password is stored as a secure hash; DataKite never displays it.':'Sign in securely to your free DataKite AI workspace.';
}
document.querySelectorAll('.auth-tab').forEach(t=>t.addEventListener('click',()=>setMode(t.dataset.mode)));
document.getElementById('signinForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const name=document.getElementById('userName').value.trim();
  const email=document.getElementById('userEmail').value.trim();
  const password=document.getElementById('userPassword').value;
  const normalizedEmail=email.toLowerCase();
  const endpoint=authMode==='register'?'/auth/register':'/auth/login';
  if(authMode==='register'){const accounts=JSON.parse(localStorage.getItem('datakite_accounts')||'[]');if(accounts.includes(normalizedEmail)){throw new Error('An account with this Gmail already exists. Please sign in instead.')}}
  const btn=document.getElementById('authSubmit');
  btn.disabled=true; btn.textContent=authMode==='register'?'Creating…':'Signing in…';
  try{
    const r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,email,password})});
    const data=await r.json();
    if(!r.ok) throw new Error(data.error||'Authentication failed.');
    localStorage.setItem('datakite_user',JSON.stringify(data.user));
    if(authMode==='register'){const accounts=JSON.parse(localStorage.getItem('datakite_accounts')||'[]');if(!accounts.includes(normalizedEmail))accounts.push(normalizedEmail);localStorage.setItem('datakite_accounts',JSON.stringify(accounts));}
    window.location.href='/app';
  }catch(err){alert(err.message)}
  finally{btn.disabled=false;setMode(authMode)}
});
document.getElementById('menu')?.addEventListener('click',()=>{const nav=document.querySelector('.topbar nav');const shown=nav.style.display==='flex';nav.style.display=shown?'none':'flex';if(!shown){nav.style.position='absolute';nav.style.top='68px';nav.style.left='0';nav.style.right='0';nav.style.padding='18px 6%';nav.style.background='#0b0d11';nav.style.borderBottom='1px solid #22252c';nav.style.flexDirection='column';nav.style.alignItems='stretch'}});
