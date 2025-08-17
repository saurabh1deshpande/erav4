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
    let partOfSpeech = '';
    try {
      const response = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(text)}`);
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data) && data[0]?.meanings?.[0]?.definitions?.[0]?.definition) {
          meaning = data[0].meanings[0].definitions[0].definition;
          partOfSpeech = data[0].meanings[0]?.partOfSpeech || '';
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
    tooltip.innerHTML = `
      <div style="display: flex; align-items: center; font-weight: bold; font-size: 17px; margin-bottom: 8px; color: #e0e0e0; letter-spacing: 0.5px;">
        <span style='display:inline-block;width:20px;height:20px;margin-right:8px;vertical-align:middle;'>
          <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='#e0e0e0' width='20' height='20'>
            <path d='M4 4v16h16V4H4zm2 2h12v12H6V6zm2 2v8h8V8H8zm2 2h4v4h-4v-4z'/>
          </svg>
        </span>
        Word Definition
      </div>
      <div style="font-size: 15px; color: #39ff14; background: #111; padding: 18px 20px; border-radius: 7px; box-shadow: 0 1px 2px rgba(0,0,0,0.10);">
        ${partOfSpeech ? `<span style='font-style:italic; color:#b0b0b0; font-size:14px;'>(${partOfSpeech})</span><br>` : ''}
        ${meaning}
      </div>
    `;
    tooltip.style.position = 'fixed';
    tooltip.style.zIndex = 99999;
    tooltip.style.background = '#000';
    tooltip.style.color = '#39ff14';
    tooltip.style.padding = '16px 18px';
    tooltip.style.borderRadius = '10px';
    tooltip.style.boxShadow = '0 4px 16px rgba(44,62,80,0.25)';
    tooltip.style.fontSize = '16px';
    tooltip.style.maxWidth = '380px';
    tooltip.style.wordBreak = 'break-word';
    tooltip.style.pointerEvents = 'none';
    tooltip.style.border = '1.5px solid #39ff14';
    // Position tooltip near mouse
    tooltip.style.left = `${event.clientX + 10}px`;
    tooltip.style.top = `${event.clientY + 10}px`;
    document.body.appendChild(tooltip);
  }, 10);
});

document.addEventListener('mousedown', removeTooltip);
