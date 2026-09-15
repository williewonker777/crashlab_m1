(() => {
  "use strict";
  const model = window.ArmModel;
  if (!model) return;
  const fmt = (n, digits=3) => (Math.abs(n)<.5*10**-digits?0:n).toFixed(digits);
  const colors = ["#B65030", "#006874", "#1D2475"];
  function project(p, view="oblique") {
    if(view==="front") return [450-440*p[1],130-440*p[2]];
    if(view==="side") return [200+440*p[0],130-440*p[2]];
    return [380+440*(.8*p[0]+.6*p[1]),115+440*(.3*p[0]-.4*p[1]-.8660254*p[2])];
  }
  function line(a,b,color,width=3,dash="") {return `<path d="M${a.join(' ')}L${b.join(' ')}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" ${dash?`stroke-dasharray="${dash}"`:""}/>`;}
  function label(p,text,color="#647080",size=23) {return `<text x="${p[0]}" y="${p[1]}" fill="${color}" font-size="${size}">${text}</text>`;}
  function chain(state,projector,color="#1D2475",ghost=false) {
    const pts=state.points.map(projector);
    let svg=pts.slice(1).map((p,i)=>line(pts[i],p,color,ghost?5:13,ghost?"8 7":"")).join("");
    if(!ghost) svg+=pts.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="${i===3?8:12}" fill="${i===3?'#00A0B0':i===1?'#FFF0DD':'#FFFFFF'}" stroke="${i===1?'#AF5900':color}" stroke-width="4"/>`).join("");
    return svg;
  }
  function renderBoard(el,state,view,ghost,fixedPoints) {
    const bounds=[...(fixedPoints||state.points),[0,-.24,0],[0,0,-.30],[.18,0,0],[0,.18,0],[0,0,.18]];
    if(ghost)bounds.push(...ghost.points);
    const frame=fixedPoints&&ghost?ghost:state;
    for(let i=0;i<3;i++)bounds.push(frame.p.map((v,j)=>v+.10*frame.R[j][i]));
    const projected=bounds.map(p=>project(p,view));
    const xs=projected.map(p=>p[0]),ys=projected.map(p=>p[1]);
    const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
    const fit=Math.min(620/(maxX-minX),310/(maxY-minY));
    const pr=p=>{const a=project(p,view);return [400+fit*(a[0]-(minX+maxX)/2),240+fit*(a[1]-(minY+maxY)/2)];};
    const origin=pr([0,0,0]);
    let svg=line(pr([0,-.24,0]),pr([0,.24,0]),"#B6BFCD",20)+line(pr([0,0,0]),pr([0,0,-.30]),"#D8DEE9",38);
    for(let i=0;i<3;i++) {
      const axis=[0,0,0];axis[i]=.18;
      svg+=line(origin,pr(axis),colors[i],3)+label(pr(axis).map((v,j)=>v+(j===0?8:-8)),['x','y','z'][i],colors[i]);
    }
    svg+=label([32,36],"torso_link 기준 · m", "#647080",22);
    if(ghost)svg+=chain(ghost,pr,"#BAC4D3",true);
    svg+=chain(state,pr);
    // TCP axes display orientation independently of the arm's projected links.
    for(let i=0;i<3;i++) {
      const end=state.p.map((v,j)=>v+.10*state.R[j][i]);
      svg+=line(pr(state.p),pr(end),colors[i],4);
    }
    const end=pr(state.p);
    svg+=label([end[0]+14,end[1]+30],"TCP", "#006874",24);
    svg+=label([36,448],"선: 링크 연결 · 주황 점: 팔꿈치 · 청록 점: TCP", "#647080",21);
    el.innerHTML=svg;
  }
  function stateText(root,state) {
    const position=root.querySelector('[data-arm-position]'), orientation=root.querySelector('[data-arm-orientation]');
    if(position)position.textContent=state.p.map(v=>fmt(v)).join(" · ");
    if(orientation)orientation.textContent=model.quaternion(state.R).map(v=>fmt(v)).join(" · ");
    root.dataset.pose=JSON.stringify({p:state.p,R:state.R});
  }
  const fk=document.querySelector('[data-arm-fk]');
  if(fk) {
    let view="oblique";
    const sliders=[...fk.querySelectorAll('[data-arm-joint]')];
    function render() {
      const q=model.radians(sliders.map(input=>Number(input.value))), state=model.forward(q);
      sliders.forEach((input,i)=>fk.querySelector(`[data-arm-angle="${i}"]`).textContent=`${input.value}°`);
      renderBoard(fk.querySelector('[data-arm-drawing]'),state,view);stateText(fk,state);
      fk.dataset.q=JSON.stringify(q);
      fk.querySelector('[data-arm-board]').setAttribute('aria-label',`왼팔 7개 관절의 순기구학. TCP 위치 ${state.p.map(v=>fmt(v)).join(', ')} 미터.`);
      fk.querySelectorAll('[data-arm-preset]').forEach(b=>b.setAttribute('aria-pressed',String(model.presets[b.dataset.armPreset].every((v,i)=>Math.abs(v-q[i])<1e-7))));
    }
    sliders.forEach(input=>input.addEventListener('input',render));
    fk.querySelectorAll('[data-arm-preset]').forEach(b=>b.addEventListener('click',()=>{
      model.presets[b.dataset.armPreset].forEach((q,i)=>sliders[i].value=Math.round(q*180/Math.PI));render();
    }));
    fk.querySelectorAll('[data-arm-view]').forEach(b=>b.addEventListener('click',()=>{
      view=b.dataset.armView;
      fk.querySelectorAll('[data-arm-view]').forEach(button=>button.setAttribute('aria-pressed',String(button===b)));render();
    }));
    render();
  }
  const ik=document.querySelector('[data-arm-ik]');
  if(ik) {
    const target=model.forward(model.presets.ready), input=ik.querySelector('[data-arm-redundancy]');
    // Keep one camera scale and center: a fixed TCP must also stay fixed on screen.
    const fixedPoints=Array.from({length:51},(_,i)=>model.inverse(target,model.presets.ready,{locked:{index:2,value:(-40+2*i)*Math.PI/180}}).state.points).flat();
    function render() {
      const result=model.inverse(target,model.presets.ready,{locked:{index:2,value:Number(input.value)*Math.PI/180}});
      ik.querySelector('[data-arm-free-angle]').textContent=`${input.value}°`;
      ik.querySelector('[data-arm-ik-status]').textContent=result.success?'같은 목표 pose 유지':'이 조건에서 수렴하지 않음';
      if(!result.success)return;
      renderBoard(ik.querySelector('[data-arm-drawing]'),result.state,'oblique',target,fixedPoints);stateText(ik,result.state);
      ik.querySelector('[data-arm-error]').textContent=`위치 ${(Math.hypot(...result.error.slice(0,3))*1000).toFixed(3)} mm · 방향 ${(Math.hypot(...result.error.slice(3))*180/Math.PI).toFixed(4)}°`;
      ik.querySelector('[data-arm-solution]').textContent=result.q.map(v=>fmt(v*180/Math.PI,1)+'°').join(' · ');
      ik.dataset.q=JSON.stringify(result.q);ik.dataset.error=JSON.stringify(result.error);
      ik.querySelector('[data-arm-board]').setAttribute('aria-label',`어깨 q3 ${input.value}도에서 다른 여섯 관절을 계산해 같은 TCP 위치와 방향을 유지한 팔 구조`);
      ik.querySelectorAll('[data-arm-solution-preset]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.armSolutionPreset)===Number(input.value))));
    }
    input.addEventListener('input',render);
    ik.querySelectorAll('[data-arm-solution-preset]').forEach(b=>b.addEventListener('click',()=>{input.value=b.dataset.armSolutionPreset;render();}));
    render();
  }
})();
