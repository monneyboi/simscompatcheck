<script>
  let sims = $state([]);
  let families = $state([]);
  let selectedSimId = $state(null);
  let rankings = $state([]);
  let loading = $state(true);
  let loadingRankings = $state(false);
  let error = $state(null);

  // Group sims by family name
  let groupedSims = $derived.by(() => {
    const groups = {};
    for (const sim of sims) {
      const familyName = sim.family_name || 'Unknown';
      if (!groups[familyName]) {
        groups[familyName] = [];
      }
      groups[familyName].push(sim);
    }
    // Sort families alphabetically, sort sims within each family by name
    const sorted = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
    for (const [, members] of sorted) {
      members.sort((a, b) => a.name.localeCompare(b.name));
    }
    return sorted;
  });

  let selectedSim = $derived(sims.find(s => s.id === selectedSimId) || null);

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

  async function selectSim(simId) {
    if (selectedSimId === simId) return;
    selectedSimId = simId;
    rankings = [];
    loadingRankings = true;
    try {
      const res = await fetch(`/api/sims/${simId}/compatibility`);
      if (!res.ok) throw new Error(`Failed to fetch compatibility: ${res.status}`);
      const data = await res.json();
      rankings = data.rankings;
    } catch (e) {
      error = e.message;
    } finally {
      loadingRankings = false;
    }
  }

  function formatInterest(key) {
    const labels = {
      travel: 'Travel',
      violence: 'Violence',
      politics: 'Politics',
      sixties: '60s/70s',
      weather: 'Weather',
      sports: 'Sports',
      music: 'Music',
      outdoors: 'Outdoors',
    };
    return labels[key] || key;
  }
</script>

<div class="layout">
  <header class="header">
    <h1>Sims 1 Compatibility Checker</h1>
  </header>

  <div class="content">
    <!-- Left panel: Sim selector -->
    <aside class="sidebar">
      <h2 class="panel-title">Sims</h2>
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
                  class:selected={selectedSimId === sim.id}
                  onclick={() => selectSim(sim.id)}
                >
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
    <main class="main-panel">
      {#if !selectedSim}
        <div class="empty-state">
          <p>Select a sim from the list to see compatibility rankings.</p>
        </div>
      {:else}
        <div class="selected-sim-header">
          <h2>
            {selectedSim.name}
            <span class="selected-family">({selectedSim.family_name})</span>
          </h2>
          <div class="selected-sim-details">
            <span class="detail-chip">{selectedSim.age}</span>
            <span class="detail-chip">{selectedSim.gender}</span>
          </div>
        </div>

        {#if loadingRankings}
          <p class="status-message">Loading compatibility data...</p>
        {:else if rankings.length === 0}
          <p class="status-message">No compatibility data available.</p>
        {:else}
          <h3 class="rankings-heading">Compatibility Rankings</h3>
          <div class="rankings-list">
            {#each rankings as ranking, i}
              <div class="ranking-card">
                <div class="ranking-header">
                  <span class="ranking-rank">#{i + 1}</span>
                  <span class="ranking-sim-name">{ranking.sim.name}</span>
                  <span class="ranking-family-name">{ranking.sim.family_name}</span>
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
                  <div class="personality-row">
                    <span class="interest-label">Personality match:</span>
                    <span class="data-value">{ranking.personality_match}</span>
                  </div>
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

  .header {
    border-bottom: 1px solid var(--color-border);
    padding: 12px 24px;
    flex-shrink: 0;
  }

  .header h1 {
    font-size: 1.1rem;
    font-weight: 600;
    letter-spacing: -0.01em;
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
    padding: 12px 16px 8px;
    flex-shrink: 0;
  }

  .sim-list {
    overflow-y: auto;
    flex: 1;
    padding-bottom: 16px;
  }

  .family-group {
    margin-bottom: 4px;
  }

  .family-name {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
    padding: 10px 16px 4px;
    background: #f8f8f8;
    border-bottom: 1px solid var(--color-border);
    border-top: 1px solid var(--color-border);
  }

  .sim-button {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: 8px 16px;
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

  .sim-name-label {
    font-weight: 500;
  }

  .sim-meta {
    font-size: 0.75rem;
    color: var(--color-muted);
    font-family: var(--font-mono);
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
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--color-border);
  }

  .selected-sim-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
  }

  .selected-family {
    font-weight: 400;
    color: var(--color-muted);
  }

  .selected-sim-details {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }

  .detail-chip {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    padding: 2px 8px;
    background: #f3f3f3;
    border: 1px solid var(--color-border);
    border-radius: 3px;
    color: var(--color-muted);
  }

  .rankings-heading {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-muted);
    margin-bottom: 12px;
  }

  .rankings-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .ranking-card {
    border: 1px solid var(--color-border);
    padding: 12px 16px;
    border-radius: 4px;
  }

  .ranking-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 8px;
  }

  .ranking-rank {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--color-muted);
    min-width: 28px;
  }

  .ranking-sim-name {
    font-weight: 600;
    font-size: 0.95rem;
  }

  .ranking-family-name {
    font-size: 0.85rem;
    color: var(--color-muted);
  }

  .ranking-score-value {
    margin-left: auto;
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 0.85rem;
    color: var(--color-accent);
  }

  .score-bar-container {
    height: 6px;
    background: #eee;
    border-radius: 3px;
    margin-bottom: 10px;
    overflow: hidden;
  }

  .score-bar {
    height: 100%;
    background: var(--color-accent);
    border-radius: 3px;
    transition: width 0.3s ease;
  }

  .ranking-details {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .interest-row, .personality-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .interest-label {
    font-size: 0.75rem;
    color: var(--color-muted);
    min-width: 54px;
  }

  .tag {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    padding: 1px 7px;
    border-radius: 3px;
    font-weight: 500;
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

  .data-value {
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }

  /* Responsive: stack on narrow screens */
  @media (max-width: 700px) {
    .content {
      flex-direction: column;
    }

    .sidebar {
      width: 100%;
      max-height: 40vh;
      border-right: none;
      border-bottom: 1px solid var(--color-border);
    }
  }
</style>
