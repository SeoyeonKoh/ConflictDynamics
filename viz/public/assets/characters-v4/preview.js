/* Plain DOM renderer: uses the same named frames and timings as the Phaser helper. */
const data = window.CHARACTER_ASSETS;
const grid = document.querySelector('#grid');
let paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
let speed = 1;
let zoom = 2;
let previous = performance.now();
let loaded = 0;
const views = [];

function render(view) {
  const animation = data.animations[view.motion];
  const name = animation.frames[view.index];
  const row = view.agent.data.frames[name];
  const { x, y, w, h } = row.frame;
  const size = row.sourceSize;
  const scale = view.agent.displayHeight * zoom / size.h;
  const image = view.agent.data.meta.size;
  Object.assign(view.viewport.style, {width: `${size.w * scale}px`, height: `${size.h * scale}px`});
  Object.assign(view.sprite.style, {
    left: `${row.spriteSourceSize.x * scale}px`, top: `${row.spriteSourceSize.y * scale}px`,
    width: `${w * scale}px`, height: `${h * scale}px`,
    backgroundSize: `${image.w * scale}px ${image.h * scale}px`,
    backgroundPosition: `${-x * scale}px ${-y * scale}px`,
  });
  view.output.textContent = name;
}

for (const agent of data.characters) {
  const card = document.createElement('article');
  card.innerHTML = '<div class="stage"><div class="viewport"><div class="sprite"></div></div></div>' +
    '<div class="info"><div class="name"><strong></strong><small></small></div><select></select>' +
    '<div class="footer"><output></output><a>Sheet ↗</a></div></div>';
  card.querySelector('strong').textContent = agent.label;
  card.querySelector('small').textContent = agent.id;
  const select = card.querySelector('select');
  select.setAttribute('aria-label', `${agent.label} animation`);
  for (const name of Object.keys(data.animations)) select.add(new Option(name, name));
  const link = card.querySelector('a');
  link.href = agent.image;
  const view = {agent, motion: 'idle', index: 0, elapsed: 0, select,
    viewport: card.querySelector('.viewport'), sprite: card.querySelector('.sprite'),
    output: card.querySelector('output')};
  view.sprite.style.backgroundImage = `url('${agent.image}')`;
  select.onchange = () => {view.motion = select.value; view.index = 0; view.elapsed = 0; render(view);};
  views.push(view);
  grid.append(card);
  render(view);
  const image = new Image();
  image.onload = () => {loaded++; document.querySelector('#loaded').textContent = `${loaded}/20 sheets · 200 frames`;};
  image.onerror = () => {view.output.textContent = 'Image failed to load'; card.dataset.error = 'true';};
  image.src = agent.image;
}

function updatePause() {
  const button = document.querySelector('#pause');
  button.textContent = paused ? 'Play' : 'Pause';
  button.setAttribute('aria-pressed', String(paused));
}
updatePause();
document.querySelector('#pause').onclick = () => {paused = !paused; updatePause();};
document.querySelector('#motion').onchange = event => {
  for (const view of views) {
    view.motion = event.target.value; view.select.value = view.motion;
    view.index = 0; view.elapsed = 0; render(view);
  }
};
document.querySelector('#speed').onchange = event => {speed = Number(event.target.value);};
document.querySelector('#zoom').onchange = event => {zoom = Number(event.target.value); views.forEach(render);};
document.querySelector('#step').onclick = () => {
  paused = true; updatePause();
  for (const view of views) {
    view.index = (view.index + 1) % data.animations[view.motion].frames.length;
    view.elapsed = 0; render(view);
  }
};
function animate(now) {
  const delta = Math.min(now - previous, 100) * speed;
  previous = now;
  if (!paused) for (const view of views) {
    view.elapsed += delta;
    const clip = data.animations[view.motion];
    while (view.elapsed >= clip.durations[view.index]) {
      view.elapsed -= clip.durations[view.index];
      view.index = (view.index + 1) % clip.frames.length;
      render(view);
    }
  }
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
