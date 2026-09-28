"use strict";
const assert = require("node:assert/strict");
const {map,createSearch,stepSearch,stereoAt}=require("../assets/js/lecture3-basics.js");
// Independent breadth-first search checks the shortest path length.
function bfs(grid){
  const q=[[...grid.start,0]], seen=new Set([grid.start.join(',')]), walls=new Set(grid.walls.map(p=>p.join(',')));
  for(let i=0;i<q.length;i++){
    const [x,y,d]=q[i];if(x===grid.goal[0]&&y===grid.goal[1])return d;
    for(const [nx,ny] of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]){
      const id=[nx,ny].join(',');if(nx<0||ny<0||nx>=grid.width||ny>=grid.height||seen.has(id)||walls.has(id))continue;
      seen.add(id);q.push([nx,ny,d+1]);
    }
  }return Infinity;
}
function check(grid){
  const s=createSearch(grid);while(!s.done){stepSearch(s);assert.ok(s.steps<=grid.width*grid.height);}
  const expected=bfs(grid);assert.equal(s.path.length?s.path.length-1:Infinity,expected);
  if(s.path.length){assert.equal(s.path[0],grid.start.join(','));assert.equal(s.path.at(-1),grid.goal.join(','));}
  s.path.forEach((id,i)=>{assert.ok(!s.walls.has(id));assert.equal(s.costs.get(id),i);if(i){const [x,y]=id.split(',').map(Number),[px,py]=s.path[i-1].split(',').map(Number);assert.equal(Math.abs(x-px)+Math.abs(y-py),1);}});
  const steps=s.steps;stepSearch(s);assert.equal(s.steps,steps);return s;
}
assert.equal(check(map).path.length-1,10);
check({width:1,height:1,start:[0,0],goal:[0,0],walls:[]});
const optional=[[1,0],[2,0],[0,1],[1,1],[2,1],[0,2],[1,2]];
for(let mask=0;mask<128;mask++)check({width:3,height:3,start:[0,0],goal:[2,2],walls:optional.filter((_,i)=>mask&(1<<i))});
assert.equal(stereoAt(1).disparity,72);assert.equal(stereoAt(2).disparity,36);assert.equal(stereoAt(4).disparity,18);
let previous=Infinity;
for(let n=10;n<=40;n++){const s=stereoAt(n/10);assert.ok(s.disparity<previous);assert.ok(Math.abs((s.left-s.right)/3-s.disparity)<1e-10);assert.ok(Math.abs(72/s.disparity-s.distance)<1e-10);previous=s.disparity;}
console.log('A*: 130 maps match BFS, including unreachable goals and ties. Stereo: all 31 slider values pass.');
