import { useEffect, useState } from "react";
export default function MaintenancePage(){
const target = new Date("2026-12-31T23:59:59").getTime();
const [now,setNow]=useState(Date.now());
useEffect(()=>{ const t=setInterval(()=>setNow(Date.now()),1000); return ()=>clearInterval(t); },[]);
const diff=Math.max(0,target-now);
const d=Math.floor(diff/(1000*60*60*24));
const h=Math.floor((diff/(1000*60*60))%24);
const m=Math.floor((diff/(1000*60))%60);
const s=Math.floor((diff/1000)%60);
return(<div style={{background:"black",minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",border:"1px solid #D4AF37"}}><div style={{textAlign:"center",color:"#D4AF37"}}><h1>MY ATELIER</h1><h2>IL CAMERINO DEL MONDO</h2><h3>TORNA IL 01.01.27 - 00:00:00</h3><div style={{fontSize:"36px",marginTop:"20px"}}>{d}G : {h}H : {m}M : {s}S</div></div></div>)
}
