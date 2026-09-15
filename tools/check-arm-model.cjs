"use strict";
const assert=require('node:assert/strict');
const m=require('../assets/js/arm-model.js');
const close=(a,b,tol=1e-9)=>assert.ok(Math.abs(a-b)<tol,`${a} ≠ ${b}`);
const norm=v=>Math.hypot(...v);
const zero=m.forward([0,0,0,0,0,0,0]);
zero.p.forEach((v,i)=>close(v,[0,.24,-.615][i]));
const quarter=m.forward([-Math.PI/2,0,0,0,0,0,0]);
quarter.p.forEach((v,i)=>close(v,[.615,.24,0][i]));
assert.throws(()=>m.forward([0]),RangeError);
for(let sample=0;sample<20;sample++) {
  const q=Array.from({length:7},(_,i)=>Math.sin(sample*1.3+i)*1.2), state=m.forward(q), J=m.jacobian(state);
  const orth=m.multiply(state.R,m.transpose(state.R));
  orth.forEach((row,i)=>row.forEach((v,j)=>close(v,i===j?1:0)));
  close(norm(m.quaternion(state.R)),1);
  for(let joint=0;joint<7;joint++) {
    const next=q.slice();next[joint]+=1e-6;
    const e=m.error(state,m.forward(next));
    e.forEach((v,i)=>close(v/1e-6,J[i][joint],5e-7));
  }
}
// Full-pose IK redundancy: elbow moves while TCP position AND orientation remain fixed.
const target=m.forward(m.presets.ready), elbows=[];
for(let degrees=-40;degrees<=60;degrees+=2) {
  const r=m.inverse(target,m.presets.ready,{locked:{index:2,value:degrees*Math.PI/180}});
  assert.ok(r.success);close(r.q[2],degrees*Math.PI/180);
  assert.ok(norm(r.error.slice(0,3))<1e-6&&norm(r.error.slice(3))<1e-5);
  elbows.push(r.state.origins[3]);
}
assert.ok(norm(elbows[0].map((v,i)=>v-elbows.at(-1)[i]))>.2);
for(const q of [m.presets.ready,m.presets.reach]) {
  const target=m.forward(q), r=m.inverse(target,q.map(v=>v+.05));
  assert.ok(r.success);
}
// The straight singular pose can converge slowly: an iterative failure is not a reachability proof.
const straightResult=m.inverse(zero,m.presets.zero.map(()=>.05));
assert.ok(straightResult.error.every(Number.isFinite));
assert.ok(norm(straightResult.error.slice(0,3))<.0001);
for(const axis of [[1,0,0],[0,1,0],[0,0,1]]) {
  const v=m.rotationVector(m.rotation(axis,Math.PI));close(norm(v),Math.PI);
}
const impossible=m.inverse({p:[5,5,5],R:zero.R},m.presets.ready);
assert.equal(impossible.success,false);
console.log('PASS: URDF 치수의 기준 자세, 140개 Jacobian 열의 유한차분, 회전 정규성, 51개 여유자유도 IK, pose 유지·불가능한 목표');
