const colors = ["#2176AB", "#F97662", "#FFBF00", "#50C878", "#B284BE"];
const svg = d3.select("svg");
let width = +svg.style("width").replace("px", "");
let height = +svg.style("height").replace("px", "");

const nSide = 20;
const threshold = 0.005;
let grid = [];
let edges = [];
let neighbors = [];
let pois = [];
let running = false;
let timer = null;

function buildSquareGrid(n) {
  grid = [];
  edges = [];
  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      grid.push([c / (n - 1), r / (n - 1)]);
      const idx = r * n + c;
      if (c < n - 1) edges.push([idx, idx + 1]);
      if (r < n - 1) edges.push([idx, idx + n]);
    }
  }
  neighbors = Array(grid.length).fill(0).map(() => []);
  edges.forEach(([a,b]) => {
    neighbors[a].push(b);
    neighbors[b].push(a);
  });
}

function initPOIs(count) {
  pois = [];
  for (let i = 0; i < count; i++) {
    pois.push([
      Math.random(),
      Math.random()
    ]);
  }
}

function draw() {
  const scaleX = d3.scaleLinear().domain([0,1]).range([0,width]);
  const scaleY = d3.scaleLinear().domain([0,1]).range([0,height]);

  const lineData = edges.map(e => {
    return {
      source: grid[e[0]],
      target: grid[e[1]]
    };
  });

  const lines = svg.selectAll(".grid-line").data(lineData, (d,i) => i);
  lines.enter()
    .append("line")
    .attr("class", "grid-line")
    .merge(lines)
    .attr("x1", d => scaleX(d.source[0]))
    .attr("y1", d => scaleY(d.source[1]))
    .attr("x2", d => scaleX(d.target[0]))
    .attr("y2", d => scaleY(d.target[1]));
  lines.exit().remove();

  const poiNodes = svg.selectAll(".poi").data(pois);
  poiNodes.enter()
    .append("circle")
    .attr("class", "poi")
    .attr("r", 6)
    .attr("fill", (d,i) => colors[i % colors.length])
    .call(d3.drag().on("drag", function(event,d){
      d[0] = Math.min(1, Math.max(0, scaleX.invert(event.x)));
      d[1] = Math.min(1, Math.max(0, scaleY.invert(event.y)));
      d3.select(this)
        .attr("cx", scaleX(d[0]))
        .attr("cy", scaleY(d[1]));
    }))
    .merge(poiNodes)
    .attr("cx", d => scaleX(d[0]))
    .attr("cy", d => scaleY(d[1]))
    .attr("fill", (d,i) => colors[i % colors.length]);
  poiNodes.exit().remove();
}

function step(alpha, beta) {
  let maxMinD = 0;
  const move = new Array(grid.length).fill(0).map(() => [0,0]);
  for (let i=0; i<grid.length; i++) {
    const n = grid[i];
    // distance to pois
    let bestJ = 0;
    let bestD = Infinity;
    for (let j=0; j<pois.length; j++) {
      const dx = pois[j][0]-n[0];
      const dy = pois[j][1]-n[1];
      const d = Math.hypot(dx,dy);
      if (d < bestD) {
        bestD = d;
        bestJ = j;
      }
    }
    maxMinD = Math.max(maxMinD, bestD);
    let vPoi = [0,0];
    if (bestD > 0) {
      vPoi = [alpha * bestD * ((pois[bestJ][0]-n[0])/bestD),
              alpha * bestD * ((pois[bestJ][1]-n[1])/bestD)];
    }
    let vCoh = [0,0];
    if (neighbors[i].length>0) {
      let cx=0,cy=0;
      neighbors[i].forEach(idx => {cx+=grid[idx][0]; cy+=grid[idx][1];});
      cx /= neighbors[i].length;
      cy /= neighbors[i].length;
      vCoh = [beta * (cx - n[0]), beta * (cy - n[1])];
    }
    let vx = vPoi[0]+vCoh[0];
    let vy = vPoi[1]+vCoh[1];
    const norm = Math.hypot(vx,vy);
    const maxStep = 0.05;
    if (norm > maxStep) {
      vx *= maxStep/norm;
      vy *= maxStep/norm;
    }
    move[i][0] = vx;
    move[i][1] = vy;
  }
  for (let i=0; i<grid.length; i++) {
    grid[i][0] += move[i][0];
    grid[i][1] += move[i][1];
  }
  draw();
  if (maxMinD < threshold) {
    stop();
  }
}

function start() {
  if (running) return;
  running = true;
  const alpha = parseFloat(d3.select("#alpha").property("value"));
  const beta = parseFloat(d3.select("#beta").property("value"));
  timer = d3.timer(() => step(alpha, beta));
}

function stop() {
  running = false;
  if (timer) timer.stop();
}

function reset() {
  buildSquareGrid(nSide);
  const npoi = parseInt(d3.select('#npoi').property('value'));
  initPOIs(npoi);
  draw();
}

d3.select('#start').on('click', start);
d3.select('#stop').on('click', stop);
d3.select('#npoi').on('change', reset);
reset();
