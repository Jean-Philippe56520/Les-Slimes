import { useEffect, useMemo, useState } from 'react';

import {
  API_BASE_URL,
  enqueueCanonicalCommand,
  fetchCanonicalSnapshot,
  fetchIdentity,
} from './api';
import type { ActorIdentity, CanonicalSnapshot } from './types';
import { WorldCanvas } from './WorldCanvas';

const POLL_INTERVAL_MS = 1200;
const HERALD_TOKEN_KEY = 'les-slimes-herald-token';

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
  const [heraldToken, setHeraldToken] = useState(() => sessionStorage.getItem(HERALD_TOKEN_KEY) ?? '');
  const [identity, setIdentity] = useState<ActorIdentity | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [commandMessage, setCommandMessage] = useState<string | null>(null);
  const [commandBusy, setCommandBusy] = useState(false);
  const [x, setX] = useState(10);
  const [y, setY] = useState(10);
  const [foodCount, setFoodCount] = useState(1);
  const [signal, setSignal] = useState('S1');
  const [signalRadius, setSignalRadius] = useState('');

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

  useEffect(() => {
    if (!heraldToken) {
      setIdentity(null);
      return;
    }
    let cancelled = false;
    void fetchIdentity(heraldToken)
      .then((actor) => {
        if (cancelled) return;
        setIdentity(actor);
        setAuthError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setIdentity(null);
      });
    return () => {
      cancelled = true;
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

  const canDepositFood = identity?.permissions.includes('world.deposit_food') ?? false;
  const canEmitSignal = identity?.permissions.includes('world.emit_signal') ?? false;

  const connectHerald = async () => {
    const token = heraldToken.trim();
    if (!token) {
      setAuthError('Jeton requis.');
      return;
    }
    try {
      const actor = await fetchIdentity(token);
      sessionStorage.setItem(HERALD_TOKEN_KEY, token);
      setHeraldToken(token);
      setIdentity(actor);
      setAuthError(null);
      setCommandMessage(null);
    } catch (reason) {
      sessionStorage.removeItem(HERALD_TOKEN_KEY);
      setIdentity(null);
      setAuthError(reason instanceof Error ? reason.message : 'Authentification impossible');
    }
  };

  const disconnectHerald = () => {
    sessionStorage.removeItem(HERALD_TOKEN_KEY);
    setHeraldToken('');
    setIdentity(null);
    setAuthError(null);
    setCommandMessage(null);
  };

  const submitCommand = async (
    commandType: 'deposit_food' | 'emit_signal',
    payload: Record<string, unknown>,
  ) => {
    if (!identity || !heraldToken) return;
    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const command = await enqueueCanonicalCommand(heraldToken, commandType, payload);
      setCommandMessage(
        `Commande #${command.sequence} mise en file comme ${command.actor_id}. Le Worker revalidera la gouvernance avant application.`,
      );
    } catch (reason) {
      setCommandMessage(reason instanceof Error ? reason.message : 'Commande refusée');
    } finally {
      setCommandBusy(false);
    }
  };

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

      <section className="herald-console">
        <div className="herald-console__header">
          <div>
            <p className="panel-kicker">CONSOLE HÉRAUT</p>
            <h2>Interventions humaines attribuées</h2>
          </div>
          {identity ? (
            <button className="secondary-button" type="button" onClick={disconnectHerald}>
              Déconnecter
            </button>
          ) : null}
        </div>

        {!identity ? (
          <div className="herald-login">
            <label>
              Jeton d'acteur
              <input
                type="password"
                value={heraldToken}
                onChange={(event) => setHeraldToken(event.target.value)}
                placeholder="Jeton Héraut"
                autoComplete="off"
              />
            </label>
            <button type="button" onClick={() => void connectHerald()}>S'authentifier</button>
            <small>Le jeton reste uniquement dans la session du navigateur et n'est jamais inclus dans le build.</small>
            {authError ? <p className="console-message console-message--error">{authError}</p> : null}
          </div>
        ) : (
          <>
            <div className="actor-strip">
              <span>Acteur authentifié</span>
              <strong>{identity.display_name}</strong>
              <code>{identity.id}</code>
              {identity.id !== 'herald' ? <em>Cette console est prévue pour le Héraut.</em> : null}
            </div>

            <div className="command-grid">
              <form
                className="command-card"
                onSubmit={(event) => {
                  event.preventDefault();
                  void submitCommand('deposit_food', { x, y, count: foodCount });
                }}
              >
                <div>
                  <span>Miracle</span>
                  <h3>Déposer de la nourriture</h3>
                </div>
                <label>X<input type="number" step="0.1" value={x} onChange={(event) => setX(Number(event.target.value))} /></label>
                <label>Y<input type="number" step="0.1" value={y} onChange={(event) => setY(Number(event.target.value))} /></label>
                <label>Quantité<input type="number" min="1" max="100" value={foodCount} onChange={(event) => setFoodCount(Number(event.target.value))} /></label>
                <button type="submit" disabled={!canDepositFood || commandBusy}>Déposer</button>
                {!canDepositFood ? <small>Permission world.deposit_food non accordée.</small> : null}
              </form>

              <form
                className="command-card"
                onSubmit={(event) => {
                  event.preventDefault();
                  const radius = signalRadius.trim() ? Number(signalRadius) : undefined;
                  void submitCommand('emit_signal', {
                    signal,
                    x,
                    y,
                    ...(radius === undefined ? {} : { radius }),
                  });
                }}
              >
                <div>
                  <span>Miracle</span>
                  <h3>Émettre un signal</h3>
                </div>
                <label>
                  Signal
                  <select value={signal} onChange={(event) => setSignal(event.target.value)}>
                    <option>S1</option><option>S2</option><option>S3</option><option>S4</option>
                  </select>
                </label>
                <label>Rayon optionnel<input type="number" min="0" step="0.1" value={signalRadius} onChange={(event) => setSignalRadius(event.target.value)} /></label>
                <button type="submit" disabled={!canEmitSignal || commandBusy}>Émettre</button>
                {!canEmitSignal ? <small>Permission world.emit_signal non accordée.</small> : null}
              </form>
            </div>
            {commandMessage ? <p className="console-message">{commandMessage}</p> : null}
          </>
        )}
      </section>

      <footer className="footer-line">
        <span>Le navigateur n'exécute aucun tick. Les interventions passent par la command queue et le Worker.</span>
        <span>
          {snapshot
            ? `Reçu ${new Date(snapshot.receivedAt).toLocaleTimeString('fr-FR')}`
            : 'Synchronisation initiale'}
        </span>
      </footer>
    </main>
  );
}
