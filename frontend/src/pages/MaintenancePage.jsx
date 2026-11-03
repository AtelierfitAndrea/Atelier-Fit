import { useEffect, useState } from "react";

const GOLD = "#D4AF37";
const googleLogin = () => {
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(window.location.origin + "/studio")}`;
};

export default function MaintenancePage(){
const target = new Date("2026-12-31T23:59:59").getTime();
const [now,setNow]=useState(Date.now());
useEffect(()=>{ const t=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(t); },[]);
const diff=Math.max(0,target-now);
const d=Math.floor(diff/(1000*60*60*24));
const h=Math.floor((diff/(1000*60*60))%24);
const m=Math.floor((diff/(1000*60))%60);
const s=Math.floor((diff/1000)%60);
if (window.location.pathname === "/fondatore") {
  return(<div style={{background:"black",minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",border:"1px solid #D4AF37"}} data-testid="founder-login-page"><button onClick={googleLogin} style={{color:GOLD,border:`1px solid ${GOLD}`,background:"transparent",padding:"12px 28px",letterSpacing:"0.2em",fontSize:"13px",cursor:"pointer"}} data-testid="founder-google-login-btn">Accedi con Google</button></div>);
}
return(<div style={{background:"black",minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",border:"1px solid #D4AF37",position:"relative"}}><div style={{textAlign:"center",color:"#D4AF37"}}><h1>MY ATELIER</h1><h2>IL CAMERINO DEL MONDO</h2><h3>TORNA IL 01.01.27 - 00:00:00</h3><div style={{fontSize:"36px",marginTop:"20px"}} data-testid="maintenance-countdown">{d}G : {h}H : {m}M : {s}S</div></div><a href="/fondatore" style={{position:"absolute",bottom:"24px",left:"50%",transform:"translateX(-50%)",color:GOLD,border:`1px solid ${GOLD}`,padding:"4px 12px",fontSize:"10px",letterSpacing:"0.2em",opacity:0.35,textDecoration:"none"}} data-testid="owner-access-btn">Accesso Proprietario</a></div>)
}
