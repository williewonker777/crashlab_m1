(function (root, factory) {
  "use strict";
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  else root.ArmModel = model;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  // ALICE M1 URDF: torso_link → left_arm_link_7. TCP offset is an explicit teaching assumption.
  const joints = [
    { name: "l_sh_p", label: "어깨 Pitch", axis: [0, 1, 0], xyz: [0, .24, 0] },
    { name: "l_sh_r", label: "어깨 Roll", axis: [1, 0, 0], xyz: [0, 0, 0] },
    { name: "l_sh_y", label: "어깨 Yaw", axis: [0, 0, 1], xyz: [0, 0, 0] },
    { name: "l_el_p", label: "팔꿈치 Pitch", axis: [0, 1, 0], xyz: [0, 0, -.26] },
    { name: "l_wr_y", label: "손목 Yaw", axis: [0, 0, 1], xyz: [0, 0, -.255] },
    { name: "l_wr_p", label: "손목 Pitch", axis: [0, 1, 0], xyz: [0, 0, 0] },
    { name: "l_wr_r", label: "손목 Roll", axis: [1, 0, 0], xyz: [0, 0, 0] }
  ];
  const tcp = [0, 0, -.10];
  const identity = () => [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const add = (a, b) => a.map((v, i) => v + b[i]);
  const subtract = (a, b) => a.map((v, i) => v - b[i]);
  const dot = (a, b) => a.reduce((s, v, i) => s + v * b[i], 0);
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  const transpose = a => a[0].map((_, i) => a.map(row => row[i]));
  const matVec = (a, v) => a.map(row => dot(row, v));
  const multiply = (a, b) => { const bt = transpose(b); return a.map(row => bt.map(col => dot(row, col))); };
  function rotation(axis, angle) {
    const [x,y,z] = axis, c = Math.cos(angle), s = Math.sin(angle), t = 1-c;
    return [[t*x*x+c,t*x*y-s*z,t*x*z+s*y],[t*x*y+s*z,t*y*y+c,t*y*z-s*x],[t*x*z-s*y,t*y*z+s*x,t*z*z+c]];
  }
  function forward(q) {
    if (q.length !== 7 || !q.every(Number.isFinite)) throw new RangeError("관절각 7개가 필요합니다.");
    let p = [0,0,0], R = identity();
    const origins = [], axes = [];
    joints.forEach((joint, i) => {
      p = add(p, matVec(R, joint.xyz));
      origins.push(p.slice()); axes.push(matVec(R, joint.axis));
      R = multiply(R, rotation(joint.axis, q[i]));
    });
    p = add(p, matVec(R, tcp));
    return { p, R, origins, axes, points: [origins[0], origins[3], origins[4], p] };
  }
  function quaternion(R) {
    const trace = R[0][0]+R[1][1]+R[2][2];
    let q;
    if (trace > 0) {
      const s = 2*Math.sqrt(trace+1);
      q = [(R[2][1]-R[1][2])/s,(R[0][2]-R[2][0])/s,(R[1][0]-R[0][1])/s,s/4];
    } else {
      let i = R[1][1] > R[0][0] ? 1 : 0;
      if (R[2][2] > R[i][i]) i = 2;
      const j = (i+1)%3, k = (i+2)%3, s = 2*Math.sqrt(Math.max(0,1+R[i][i]-R[j][j]-R[k][k]));
      q = [0,0,0,0];q[i]=s/4;q[j]=(R[j][i]+R[i][j])/s;q[k]=(R[k][i]+R[i][k])/s;q[3]=(R[k][j]-R[j][k])/s;
    }
    const norm = Math.hypot(...q), sign = q[3] < 0 ? -1 : 1;
    return q.map(v => sign*v/norm);
  }
  function rotationVector(R) {
    const q = quaternion(R), n = Math.hypot(q[0],q[1],q[2]);
    if (n < 1e-12) return q.slice(0,3).map(v => 2*v);
    const angle = 2*Math.atan2(n,q[3]);
    return q.slice(0,3).map(v => angle*v/n);
  }
  function error(current, target) {
    return [...subtract(target.p,current.p), ...rotationVector(multiply(target.R,transpose(current.R)))];
  }
  function jacobian(state) {
    return transpose(state.axes.map((axis,i) => [...cross(axis,subtract(state.p,state.origins[i])),...axis]));
  }
  function linearSolve(matrix, vector) {
    const n = vector.length, a = matrix.map((row,i) => [...row,vector[i]]);
    for (let k=0;k<n;k++) {
      let pivot=k; for(let i=k+1;i<n;i++)if(Math.abs(a[i][k])>Math.abs(a[pivot][k]))pivot=i;
      if(Math.abs(a[pivot][k])<1e-14)return null;
      [a[k],a[pivot]]=[a[pivot],a[k]];
      const divisor=a[k][k];for(let j=k;j<=n;j++)a[k][j]/=divisor;
      for(let i=0;i<n;i++)if(i!==k){const m=a[i][k];for(let j=k;j<=n;j++)a[i][j]-=m*a[k][j];}
    }
    return a.map(row=>row[n]);
  }
  // Damped least squares; orientation weight converts rad to a comparable teaching length scale.
  // Only the optional selected joint is fixed. There is no physical limit/collision model here.
  function inverse(target, seed, options = {}) {
    let q=seed.slice();
    const locked=options.locked, weight=.25, damping=.008;
    if(locked)q[locked.index]=locked.value;
    const free=joints.map((_,i)=>i).filter(i=>!locked||i!==locked.index);
    for(let iteration=0;iteration<300;iteration++) {
      const state=forward(q), e=error(state,target);
      if(Math.hypot(...e.slice(0,3))<1e-6 && Math.hypot(...e.slice(3))<1e-5) return {q,state,success:true,iteration,error:e};
      const J=jacobian(state).map((row,i)=>free.map(j=>row[j]*(i<3?1:weight)));
      const A=multiply(J,transpose(J)).map((row,i)=>row.map((v,j)=>v+(i===j?damping*damping:0)));
      const y=linearSolve(A,e.map((v,i)=>v*(i<3?1:weight)));
      if(!y)break;
      const delta=matVec(transpose(J),y), scale=Math.min(1,.22/Math.max(1e-12,Math.hypot(...delta)));
      free.forEach((index,i)=>{q[index]+=delta[i]*scale;});
    }
    const state=forward(q);return {q,state,success:false,iteration:300,error:error(state,target)};
  }
  const radians = degrees => degrees.map(v=>v*Math.PI/180);
  const presets = {
    ready: radians([-30,25,10,-70,15,25,0]),
    reach: radians([-65,15,10,-35,10,20,0]),
    zero: [0,0,0,0,0,0,0]
  };
  return {joints,tcp,forward,quaternion,jacobian,inverse,error,radians,presets,rotation,rotationVector,multiply,transpose,matVec};
});
