import { useEffect, useMemo, useState } from 'react';

import { API_BASE_URL, fetchCanonicalSnapshot } from './api';
import type { CanonicalSnapshot } from './types';
import { WorldCanvas } from './WorldCanvas';

const POLL_INTERVAL_MS = 1200;

function formatMetric(value: number, digits = 0): string {
  return new Intl.NumberFormat('fr-FR', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

function shortDigest(digest: string): string {
  if (digest.length <= 18) return digest;
  return `${digest.slice(0, 10)}…${digest.slice(-7)}`;
}

function statusLabel(snapshot: CanonicalSnapshot | null): { label: string; tone: string } {
  if (!snapshot) return { label: 'Connexion', tone: 'neutral' };
  if (!snapshot.health.writer_lease.valid) return { label: 'Worker absent', tone: 'danger' };
  if (snapshot.health.ticks_due > 3) return { label: 'Rattrapage', tone: 'warning' };
  return { label: 'Monde vivant', tone: 'ok' };
}

export default function App() {
  const [snapshot, setSnapshot] = useState<CanonicalSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let active = true;
    let timeoutId: number | undefined;
    let controller: AbortController | null = null;

    const poll = async () => {
      controller = new AbortController();
      setRefreshing(true);
      try {
        const next = await fetchCanonicalSnapshot(controller.signal);
        if (!active) return;
        setSnapshot(next);
        setError(null);
      } catch (reason) {
        if (!active || (reason instanceof DOMException && reason.name === 'AbortError')) return;
        setError(reason instanceof Error ? reason.message : 'Erreur API inconnue');
      } finally {
        if (active) {
          setRefreshing(false);
          timeoutId = window.setTimeout(poll, POLL_INTERVAL_MS);
        }
      }
    };

    void poll();
    return () => {
      active = false;
      controller?.abort();
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, []);

  const status = statusLabel(snapshot);
  const generation = snapshot?.world.max_generation ?? 0;
  const actionCounts = useMemo(() => {
    if (!snapshot) return [] as Array<[string, number]>;
    const counts = new Map<string, number>();
    for (const slime of snapshot.slimes.slimes) {
      if (!slime.alive) continue;
      counts.set(slime.current_action, (counts.get(slime.current_action) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);
  }, [snapshot]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">OBSERVATOIRE CANONIQUE</p>
          <h1>Les Slimes</h1>
        </div>
        <div className={`world-status world-status--${status.tone}`}>
          <span className="world-status__dot" />
          <span>{status.label}</span>
          {refreshing ? <span className="world-status__pulse">sync</span> : null}
        </div>
      </header>

      {error ? (
        <section className="alert" role="alert">
          <strong>API canonique inaccessible.</strong>
          <span>{error}</span>
          {!API_BASE_URL ? (
            <span>Configure VITE_API_BASE_URL sur le frontend Netlify.</span>
          ) : null}
        </section>
      ) : null}

      <section className="dashboard-grid">
        <article className="world-panel">
          <div className="panel-heading">
            <div>
              <p className="panel-kicker">MONDE 2D</p>
              <h2>État vivant</h2>
            </div>
            <div className="tick-block">
              <span>tick</span>
              <strong>{snapshot ? formatMetric(snapshot.world.tick) : '—'}</strong>
            </div>
          </div>
          <WorldCanvas snapshot={snapshot} />
          <div className="world-legend">
            <span><i className="legend-dot legend-dot--slime" />Slime</span>
            <span><i className="legend-dot legend-dot--food" />Ressource</span>
            <span>Couleur = génération</span>
            <span>Rayon = énergie</span>
          </div>
        </article>

        <aside className="side-panel">
          <section className="metric-grid">
            <article className="metric-card metric-card--primary">
              <span>Population</span>
              <strong>{snapshot ? formatMetric(snapshot.world.population) : '—'}</strong>
              <small>Slimes vivants</small>
            </article>
            <article className="metric-card">
              <span>Ressources</span>
              <strong>{snapshot ? formatMetric(snapshot.world.food_count) : '—'}</strong>
              <small>Nourritures présentes</small>
            </article>
            <article className="metric-card">
              <span>Génération max</span>
              <strong>{snapshot ? `G${generation}` : '—'}</strong>
              <small>Profondeur de lignée</small>
            </article>
            <article className="metric-card">
              <span>Énergie moyenne</span>
              <strong>{snapshot ? formatMetric(snapshot.world.mean_energy, 1) : '—'}</strong>
              <small>Santé {snapshot ? formatMetric(snapshot.world.mean_health, 1) : '—'}</small>
            </article>
          </section>

          <section className="detail-card">
            <div className="detail-card__heading">
              <span>Cycle biologique</span>
              <strong>{snapshot ? `${snapshot.world.births} / ${snapshot.world.deaths}` : '—'}</strong>
            </div>
            <div className="detail-row"><span>Naissances</span><b>{snapshot ? snapshot.world.births : '—'}</b></div>
            <div className="detail-row"><span>Décès</span><b>{snapshot ? snapshot.world.deaths : '—'}</b></div>
            <div className="detail-row"><span>Retard runtime</span><b>{snapshot ? `${formatMetric(snapshot.health.lag_seconds, 1)} s` : '—'}</b></div>
            <div className="detail-row"><span>Commandes pending</span><b>{snapshot ? snapshot.health.pending_commands : '—'}</b></div>
          </section>

          <section className="detail-card">
            <div className="detail-card__heading">
              <span>Comportements</span>
              <strong>{snapshot ? snapshot.slimes.slimes.length : '—'}</strong>
            </div>
            {actionCounts.length ? actionCounts.map(([action, count]) => (
              <div className="detail-row" key={action}>
                <span>{action}</span>
                <b>{count}</b>
              </div>
            )) : <p className="empty-state">En attente du monde…</p>}
          </section>

          <section className="digest-card">
            <span>Digest scientifique</span>
            <code title={snapshot?.world.state_digest}>{snapshot ? shortDigest(snapshot.world.state_digest) : '—'}</code>
            <small>État biologique, indépendant de la gouvernance.</small>
          </section>
        </aside>
      </section>

      <footer className="footer-line">
        <span>Lecture seule — le navigateur n’exécute aucun tick.</span>
        <span>
          {snapshot
            ? `Reçu ${new Date(snapshot.receivedAt).toLocaleTimeString('fr-FR')}`
            : 'Synchronisation initiale'}
        </span>
      </footer>
    </main>
  );
}
