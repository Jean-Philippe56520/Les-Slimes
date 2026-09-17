import { useEffect, useRef } from 'react';
import { Application, Graphics } from 'pixi.js';

import type { CanonicalSnapshot, SlimeProjection } from './types';

interface WorldCanvasProps {
  snapshot: CanonicalSnapshot | null;
}

const GENERATION_COLORS = [
  0x73e6a9,
  0x69d5e7,
  0x91b7ff,
  0xc1a6ff,
  0xf3a8d3,
  0xffbe8a,
  0xd6df79,
];

function slimeColor(slime: SlimeProjection): number {
  return GENERATION_COLORS[slime.generation % GENERATION_COLORS.length];
}

function drawWorld(app: Application, snapshot: CanonicalSnapshot): void {
  const removed = app.stage.removeChildren();
  for (const child of removed) child.destroy();

  const screenWidth = Math.max(1, app.screen.width);
  const screenHeight = Math.max(1, app.screen.height);
  const padding = Math.min(34, Math.max(14, Math.min(screenWidth, screenHeight) * 0.05));
  const usableWidth = Math.max(1, screenWidth - padding * 2);
  const usableHeight = Math.max(1, screenHeight - padding * 2);
  const scale = Math.min(
    usableWidth / Math.max(1, snapshot.world.width),
    usableHeight / Math.max(1, snapshot.world.height),
  );
  const worldWidth = snapshot.world.width * scale;
  const worldHeight = snapshot.world.height * scale;
  const originX = (screenWidth - worldWidth) / 2;
  const originY = (screenHeight - worldHeight) / 2;

  const frame = new Graphics()
    .roundRect(originX, originY, worldWidth, worldHeight, 18)
    .fill({ color: 0x0b1814, alpha: 0.96 })
    .stroke({ color: 0x285044, width: 1, alpha: 0.9 });
  app.stage.addChild(frame);

  const grid = new Graphics();
  const divisions = 8;
  for (let index = 1; index < divisions; index += 1) {
    const x = originX + (worldWidth * index) / divisions;
    const y = originY + (worldHeight * index) / divisions;
    grid.moveTo(x, originY).lineTo(x, originY + worldHeight);
    grid.moveTo(originX, y).lineTo(originX + worldWidth, y);
  }
  grid.stroke({ color: 0x17352d, width: 1, alpha: 0.42 });
  app.stage.addChild(grid);

  const foods = new Graphics();
  for (const food of snapshot.foods.foods) {
    const x = originX + food.x * scale;
    const y = originY + food.y * scale;
    const radius = Math.max(1.7, Math.min(3.8, 1.6 + food.nutrition / 28));
    foods.circle(x, y, radius).fill({ color: 0xf2d36b, alpha: 0.75 });
  }
  app.stage.addChild(foods);

  for (const slime of snapshot.slimes.slimes) {
    if (!slime.alive) continue;
    const x = originX + slime.x * scale;
    const y = originY + slime.y * scale;
    const vitality = Math.max(0.35, Math.min(1, (slime.energy + slime.health) / 200));
    const radius = Math.max(4.5, Math.min(9, 4.5 + slime.energy / 24));
    const color = slimeColor(slime);

    const body = new Graphics()
      .circle(0, 0, radius)
      .fill({ color, alpha: 0.58 + vitality * 0.35 })
      .stroke({ color: 0xe4fff2, width: 1, alpha: 0.24 + vitality * 0.35 });
    body.circle(-radius * 0.3, -radius * 0.32, Math.max(1, radius * 0.22)).fill({
      color: 0xffffff,
      alpha: 0.42,
    });
    body.moveTo(0, 0).lineTo(Math.cos(slime.heading) * radius * 1.45, Math.sin(slime.heading) * radius * 1.45);
    body.stroke({ color: 0xffffff, width: 1, alpha: 0.3 });
    body.position.set(x, y);
    body.alpha = slime.health < 30 ? 0.58 : 1;
    app.stage.addChild(body);
  }
}

export function WorldCanvas({ snapshot }: WorldCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const snapshotRef = useRef<CanonicalSnapshot | null>(snapshot);

  useEffect(() => {
    snapshotRef.current = snapshot;
    if (snapshot && appRef.current) drawWorld(appRef.current, snapshot);
  }, [snapshot]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const app = new Application();
    let disposed = false;

    void app
      .init({
        resizeTo: host,
        antialias: true,
        autoDensity: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        backgroundAlpha: 0,
      })
      .then(() => {
        if (disposed) {
          app.destroy();
          return;
        }
        app.canvas.className = 'world-canvas__surface';
        host.appendChild(app.canvas);
        appRef.current = app;
        if (snapshotRef.current) drawWorld(app, snapshotRef.current);
      });

    const resizeObserver = new ResizeObserver(() => {
      if (appRef.current && snapshotRef.current) {
        requestAnimationFrame(() => {
          if (appRef.current && snapshotRef.current) {
            drawWorld(appRef.current, snapshotRef.current);
          }
        });
      }
    });
    resizeObserver.observe(host);

    return () => {
      disposed = true;
      resizeObserver.disconnect();
      if (appRef.current === app) appRef.current = null;
      app.canvas.remove();
      app.destroy();
    };
  }, []);

  return (
    <div className="world-canvas" ref={hostRef}>
      {!snapshot ? <div className="world-canvas__placeholder">Connexion au monde canonique…</div> : null}
    </div>
  );
}
