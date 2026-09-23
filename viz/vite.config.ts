import { createReadStream, existsSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { defineConfig } from 'vite';

// Replay reads journals straight from the repo's git-ignored runs/ directory (dev server only).
const RUNS = resolve(__dirname, '../runs');

function runs(dir: string, depth = 0): string[] {
  if (existsSync(join(dir, 'frames.jsonl'))) return [relative(RUNS, dir).split(sep).join('/')];
  if (depth > 2) return [];
  return readdirSync(dir)
    .filter(name => statSync(join(dir, name)).isDirectory())
    .flatMap(name => runs(join(dir, name), depth + 1));
}

export default defineConfig({
  plugins: [{
    name: 'runs',
    configureServer(server) {
      server.middlewares.use('/runs', (req, res, next) => {
        const path = resolve(RUNS, '.' + decodeURIComponent((req.url ?? '/').split('?')[0]));
        if (path !== RUNS && !path.startsWith(RUNS + sep)) return next();
        if (path === RUNS) {
          res.setHeader('Content-Type', 'application/json');
          return res.end(JSON.stringify(existsSync(RUNS) ? runs(RUNS).sort() : []));
        }
        if (!/\.jsonl$/.test(path) || !existsSync(path)) {
          res.statusCode = 404;
          return res.end('not found');
        }
        res.setHeader('Content-Type', 'text/plain; charset=utf-8');
        createReadStream(path).pipe(res);
      });
    },
  }],
});
