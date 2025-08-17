// Listen for mouseup events to detect text selection
function removeTooltip() {
  const existing = document.getElementById('highlight-meaning-tooltip');
  if (existing) existing.remove();
}

document.addEventListener('mouseup', async (event) => {
  setTimeout(async () => {
    removeTooltip();
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : '';
    if (text.length === 0) return;

    // Fetch meaning from dictionary API
    let meaning = 'Loading...';
    try {
      const response = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(text)}`);
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data[0]?.meanings?.[0]?.definitions?.[0]?.definition) {
          meaning = data[0].meanings[0].definitions[0].definition;
        } else {
          meaning = 'No definition found.';
        }
      } else {
        meaning = 'No definition found.';
      }
    } catch (e) {
      meaning = 'Error fetching meaning.';
    }

    // Create tooltip
    const tooltip = document.createElement('div');
    tooltip.id = 'highlight-meaning-tooltip';
    tooltip.textContent = meaning;
    tooltip.style.position = 'fixed';
    tooltip.style.zIndex = 99999;
    tooltip.style.background = '#222';
    tooltip.style.color = '#fff';
    tooltip.style.padding = '8px 12px';
    tooltip.style.borderRadius = '6px';
    tooltip.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
    tooltip.style.fontSize = '16px';
    tooltip.style.maxWidth = '300px';
    tooltip.style.wordBreak = 'break-word';
    tooltip.style.pointerEvents = 'none';
    // Position tooltip near mouse
    tooltip.style.left = `${event.clientX + 10}px`;
    tooltip.style.top = `${event.clientY + 10}px`;
    document.body.appendChild(tooltip);
  }, 10);
});

document.addEventListener('mousedown', removeTooltip);
