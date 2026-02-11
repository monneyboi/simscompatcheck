<script>
  let sims = $state([]);
  let families = $state([]);
  let rankings = $state([]);
  let loading = $state(true);
  let loadingRankings = $state(false);
  let error = $state(null);
  let showKnownOnly = $state(false);
  let sidebarFilter = $state('');
  let rankingsFilter = $state('');

  // --- Routing ---
  let currentPath = $state(window.location.pathname);
  let routeSimId = $derived.by(() => {
    const match = currentPath.match(/^\/sim\/(\d+)$/);
    return match ? parseInt(match[1]) : null;
  });

  function navigateTo(path) {
    history.pushState(null, '', path);
    currentPath = path;
  }

  // Group sims by family name, filtered by sidebar search
  let groupedSims = $derived.by(() => {
    const q = sidebarFilter.toLowerCase().trim();
    const filtered = q
      ? sims.filter(s => s.name.toLowerCase().includes(q) || (s.family_name || '').toLowerCase().includes(q))
      : sims;
    const groups = {};
    for (const sim of filtered) {
      const familyName = sim.family_name || 'Unknown';
      if (!groups[familyName]) {
        groups[familyName] = [];
      }
      groups[familyName].push(sim);
    }
    const sorted = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
    for (const [, members] of sorted) {
      members.sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  });

  let selectedSim = $derived(sims.find(s => s.id === routeSimId) || null);

  let filteredRankings = $derived.by(() => {
    let result = showKnownOnly ? rankings.filter(r => r.relationship_daily !== null) : rankings;
    const q = rankingsFilter.toLowerCase().trim();
    if (q) {
      result = result.filter(r => r.sim.name.toLowerCase().includes(q) || (r.sim.family_name || '').toLowerCase().includes(q));
    }
    return result;
  });

  // Fetch sims and families on mount
  $effect(() => {
    fetchData();
  });

  async function fetchData() {
    try {
      loading = true;
      error = null;
      const [simsRes, familiesRes] = await Promise.all([
        fetch('/api/sims'),
        fetch('/api/families'),
      ]);
      if (!simsRes.ok) throw new Error(`Failed to fetch sims: ${simsRes.status}`);
      if (!familiesRes.ok) throw new Error(`Failed to fetch families: ${familiesRes.status}`);
      const simsData = await simsRes.json();
      const familiesData = await familiesRes.json();
      sims = simsData.sims;
      families = familiesData.families;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // Fetch rankings whenever routeSimId changes
  $effect(() => {
    const simId = routeSimId;
    if (!simId) {
      rankings = [];
      return;
    }
    rankings = [];
    rankingsFilter = '';
    loadingRankings = true;
    fetch(`/api/sims/${simId}/compatibility`)
      .then(res => {
        if (!res.ok) throw new Error(`Failed to fetch compatibility: ${res.status}`);
        return res.json();
      })
      .then(data => {
        if (routeSimId === simId) rankings = data.rankings;
      })
      .catch(e => { error = e.message; })
      .finally(() => {
        if (routeSimId === simId) loadingRankings = false;
      });
  });

  $effect(() => {
    const onPopState = () => currentPath = window.location.pathname;
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  });

  function formatInterest(key) {
    const labels = {
      exercise: 'Exercise',
      food: 'Food',
      parties: 'Parties',
      style: 'Style',
      hollywood: 'Hollywood',
      travel: 'Travel',
      violence: 'Crime',
      politics: 'Politics',
      sixties: '60s/70s',
      weather: 'Weather',
      sports: 'Sports',
      music: 'Music',
      outdoors: 'Outdoors',
      technology: 'Technology',
      romance: 'Romance',
    };
    return labels[key] || key;
  }
</script>

<div class="layout">
  <div class="content">
    <!-- Left panel: Sim selector -->
    <aside class="sidebar" class:mobile-hidden={routeSimId !== null}>
      <h2 class="panel-title">Sims</h2>
      <div class="filter-input-wrap">
        <input
          class="filter-input"
          type="text"
          placeholder="Filter sims..."
          bind:value={sidebarFilter}
        />
        {#if sidebarFilter}
          <button class="filter-clear" onclick={() => sidebarFilter = ''}>×</button>
        {/if}
      </div>
      {#if loading}
        <p class="status-message">Loading sims...</p>
      {:else if error && sims.length === 0}
        <p class="status-message error-text">{error}</p>
      {:else if sims.length === 0}
        <p class="status-message">No sims found.</p>
      {:else}
        <nav class="sim-list">
          {#each groupedSims as [familyName, members]}
            <div class="family-group">
              <h3 class="family-name">{familyName}</h3>
              {#each members as sim}
                <button
                  class="sim-button"
                  class:selected={routeSimId === sim.id}
                  onclick={() => navigateTo(`/sim/${sim.id}`)}
                >
                  <img
                    class="sim-portrait-small"
                    src="/api/sims/{sim.id}/portrait"
                    alt=""
                    onerror={(e) => e.target.style.display = 'none'}
                  />
                  <span class="sim-name-label">{sim.name}</span>
                  <span class="sim-meta">{sim.age} / {sim.gender}</span>
                </button>
              {/each}
            </div>
          {/each}
        </nav>
      {/if}
    </aside>

    <!-- Right panel: Compatibility rankings -->
    <main class="main-panel" class:mobile-hidden={routeSimId === null}>
      {#if !selectedSim}
        <div class="empty-state">
          <p>Select a sim from the list to see compatibility rankings.</p>
        </div>
      {:else}
        <button class="back-button" onclick={() => navigateTo('/')}>&larr; All sims</button>
        <div class="selected-sim-header">
          <img
            class="selected-sim-portrait"
            src="/api/sims/{selectedSim.id}/portrait"
            alt=""
            onerror={(e) => e.target.style.display = 'none'}
          />
          <div class="selected-sim-info">
            <h2>
              {selectedSim.name}
              <span class="selected-family">{selectedSim.family_name}</span>
            </h2>
            <div class="selected-sim-details">
              <span class="detail-chip">{selectedSim.age}</span>
              <span class="detail-chip">{selectedSim.gender}</span>
              {#if selectedSim.zodiac}
                <span class="detail-chip">{selectedSim.zodiac}</span>
              {/if}
            </div>
          </div>
        </div>

        {#if loadingRankings}
          <p class="status-message">Loading compatibility data...</p>
        {:else if rankings.length === 0}
          <p class="status-message">No compatibility data available.</p>
        {:else}
          <div class="rankings-toolbar">
            <h3 class="rankings-heading">Compatibility Rankings</h3>
            <div class="rankings-toolbar-right">
              <div class="filter-input-wrap filter-input-wrap--inline">
                <input
                  class="filter-input"
                  type="text"
                  placeholder="Filter results..."
                  bind:value={rankingsFilter}
                />
                {#if rankingsFilter}
                  <button class="filter-clear" onclick={() => rankingsFilter = ''}>×</button>
                {/if}
              </div>
              <label class="filter-toggle">
                <input type="checkbox" bind:checked={showKnownOnly} />
                Known sims only
              </label>
            </div>
          </div>
          <div class="rankings-list">
            {#each filteredRankings as ranking, i}
              <div class="ranking-card">
                <div class="ranking-header">
                  <span class="ranking-rank">#{i + 1}</span>
                  <img
                    class="sim-portrait"
                    src="/api/sims/{ranking.sim.id}/portrait"
                    alt=""
                    onerror={(e) => e.target.style.display = 'none'}
                  />
                  <div class="ranking-sim-identity">
                    <span class="ranking-sim-name">{ranking.sim.name}</span>
                    <span class="ranking-family-name">{ranking.sim.family_name}</span>
                  </div>
                  <span class="ranking-score-value">{ranking.score}</span>
                </div>

                <div class="score-bar-container">
                  <div
                    class="score-bar"
                    style="width: {(ranking.score / 1000) * 100}%"
                  ></div>
                </div>

                <div class="ranking-details">
                  {#if ranking.common_interests.length > 0}
                    <div class="interest-row">
                      <span class="interest-label">Common:</span>
                      {#each ranking.common_interests as interest}
                        <span class="tag tag-green">{formatInterest(interest)}</span>
                      {/each}
                    </div>
                  {/if}
                  {#if ranking.risky_topics.length > 0}
                    <div class="interest-row">
                      <span class="interest-label">Risky:</span>
                      {#each ranking.risky_topics as topic}
                        <span class="tag tag-red">{formatInterest(topic)}</span>
                      {/each}
                    </div>
                  {/if}
                  {#if ranking.sim.interaction_tips && ranking.sim.interaction_tips.length > 0}
                    <div class="interest-row">
                      <span class="interest-label">Tips:</span>
                      {#each ranking.sim.interaction_tips as tip}
                        <span class="tag tag-blue">{tip}</span>
                      {/each}
                    </div>
                  {/if}
                  {#if ranking.relationship_daily !== null}
                    <div class="relationship-row">
                      <span class="interest-label">Relationship:</span>
                      <span class="data-value" class:rel-positive={ranking.relationship_daily > 0} class:rel-negative={ranking.relationship_daily < 0}>
                        {ranking.relationship_daily}
                      </span>
                      <span class="rel-detail">daily</span>
                      <span class="data-value" class:rel-positive={ranking.relationship_lifetime > 0} class:rel-negative={ranking.relationship_lifetime < 0}>
                        {ranking.relationship_lifetime}
                      </span>
                      <span class="rel-detail">lifetime</span>
                      {#if ranking.is_friend}
                        <span class="tag tag-green">Friend</span>
                      {/if}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      {/if}
    </main>
  </div>
</div>

<style>
  .layout {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }

  .content {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  /* Left panel */
  .sidebar {
    width: 280px;
    flex-shrink: 0;
    border-right: 1px solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .panel-title {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-muted);
    padding: 24px 16px 8px;
    flex-shrink: 0;
  }

  .filter-input-wrap {
    position: relative;
    padding: 0 12px 8px;
    flex-shrink: 0;
  }

  .filter-input-wrap--inline {
    padding: 0;
  }

  .filter-input {
    width: 100%;
    padding: 5px 24px 5px 8px;
    font-family: var(--font-sans);
    font-size: 0.8rem;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    background: #fff;
    color: var(--color-text);
    outline: none;
    box-sizing: border-box;
  }

  .filter-input:focus {
    border-color: var(--color-accent);
  }

  .filter-input::placeholder {
    color: var(--color-muted);
  }

  .filter-clear {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    cursor: pointer;
    color: var(--color-muted);
    font-size: 1rem;
    line-height: 1;
    padding: 0 2px;
  }

  .filter-input-wrap--inline .filter-clear {
    right: 4px;
  }

  .sim-list {
    overflow-y: auto;
    flex: 1;
    padding-bottom: 16px;
  }

  .family-group {
    margin-bottom: 0;
  }

  .family-name {
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
    padding: 8px 16px 4px;
    background: #f8f8f8;
    border-bottom: 1px solid var(--color-border);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .sim-button {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 16px;
    background: none;
    border: none;
    border-bottom: 1px solid #eee;
    cursor: pointer;
    font-family: var(--font-sans);
    font-size: 0.875rem;
    color: var(--color-text);
    text-align: left;
    transition: background 0.1s;
  }

  .sim-button:hover {
    background: #f0f4ff;
  }

  .sim-button.selected {
    background: var(--color-accent);
    color: #fff;
  }

  .sim-button.selected .sim-meta {
    color: rgba(255, 255, 255, 0.75);
  }

  .sim-portrait-small {
    width: 24px;
    height: 24px;
    border-radius: 2px;
    image-rendering: pixelated;
    flex-shrink: 0;
  }

  .sim-name-label {
    font-weight: 500;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sim-meta {
    font-size: 0.7rem;
    color: var(--color-muted);
    font-family: var(--font-mono);
    flex-shrink: 0;
  }

  /* Right panel */
  .main-panel {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--color-muted);
    font-size: 0.95rem;
  }

  .status-message {
    padding: 16px;
    color: var(--color-muted);
    font-size: 0.875rem;
  }

  .error-text {
    color: var(--color-red);
  }

  .selected-sim-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--color-border);
  }

  .selected-sim-portrait {
    width: 48px;
    height: 48px;
    border-radius: 3px;
    image-rendering: pixelated;
    flex-shrink: 0;
  }

  .selected-sim-info h2 {
    font-size: 1.2rem;
    font-weight: 600;
    line-height: 1.3;
  }

  .selected-family {
    font-weight: 400;
    color: var(--color-muted);
    font-size: 0.9rem;
  }

  .selected-sim-details {
    display: flex;
    gap: 6px;
    margin-top: 4px;
  }

  .detail-chip {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    padding: 1px 6px;
    background: #f3f3f3;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-muted);
  }

  .rankings-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .rankings-heading {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-muted);
  }

  .rankings-toolbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .filter-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--color-muted);
    cursor: pointer;
    user-select: none;
  }

  .filter-toggle input {
    accent-color: var(--color-accent);
  }

  .rankings-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .ranking-card {
    border: 1px solid var(--color-border);
    padding: 12px 16px;
    border-radius: 4px;
  }

  .ranking-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
  }

  .ranking-rank {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--color-muted);
    min-width: 24px;
    text-align: right;
    flex-shrink: 0;
  }

  .sim-portrait {
    width: 36px;
    height: 36px;
    border-radius: 2px;
    image-rendering: pixelated;
    flex-shrink: 0;
  }

  .ranking-sim-identity {
    display: flex;
    align-items: baseline;
    gap: 6px;
    min-width: 0;
  }

  .ranking-sim-name {
    font-weight: 600;
    font-size: 0.95rem;
    white-space: nowrap;
  }

  .ranking-family-name {
    font-size: 0.8rem;
    color: var(--color-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ranking-score-value {
    margin-left: auto;
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--color-accent);
    flex-shrink: 0;
  }

  .score-bar-container {
    height: 4px;
    background: #eee;
    border-radius: 2px;
    margin-bottom: 8px;
    overflow: hidden;
  }

  .score-bar {
    height: 100%;
    background: var(--color-accent);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .ranking-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .interest-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 6px;
  }

  .interest-label {
    font-size: 0.7rem;
    color: var(--color-muted);
    min-width: 72px;
    flex-shrink: 0;
  }

  .tag {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    padding: 1px 6px;
    border-radius: 3px;
    font-weight: 500;
    white-space: nowrap;
  }

  .tag-green {
    background: #dcfce7;
    color: var(--color-green);
    border: 1px solid #bbf7d0;
  }

  .tag-red {
    background: #fef2f2;
    color: var(--color-red);
    border: 1px solid #fecaca;
  }

  .tag-blue {
    background: #eff6ff;
    color: var(--color-accent);
    border: 1px solid #bfdbfe;
  }

  .data-value {
    font-family: var(--font-mono);
    font-size: 0.75rem;
  }

  .rel-positive {
    color: var(--color-green);
  }

  .rel-negative {
    color: var(--color-red);
  }

  .rel-detail {
    font-size: 0.65rem;
    color: var(--color-muted);
  }

  .relationship-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px 6px;
  }

  .back-button {
    display: none;
  }

  /* Mobile: separate screens */
  @media (max-width: 700px) {
    .content {
      flex-direction: column;
    }

    .sidebar {
      width: 100%;
      flex: 1;
      border-right: none;
    }

    .main-panel {
      width: 100%;
      flex: 1;
      padding: 16px;
    }

    .mobile-hidden {
      display: none;
    }

    .back-button {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: none;
      border: none;
      color: var(--color-accent);
      font-family: var(--font-sans);
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      padding: 0 0 12px;
    }

    .rankings-toolbar {
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }

    .rankings-toolbar-right {
      width: 100%;
    }

    .filter-input-wrap--inline {
      flex: 1;
    }

    .ranking-sim-identity {
      flex-direction: column;
      gap: 0;
    }

    .interest-label {
      min-width: 0;
    }
  }
</style>
