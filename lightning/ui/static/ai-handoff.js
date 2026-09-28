document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-prompt]');
  if (!button) return;
  const area = button.closest('.ai-handoff').querySelector('#ai-import-prompt');
  const status = button.closest('.ai-handoff').querySelector('[data-copy-status]');
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(area.value);
    } else {
      area.focus();
      area.select();
      if (!document.execCommand('copy')) throw new Error('Copy unavailable');
    }
    status.textContent = 'Prompt copied.';
  } catch (_) {
    area.focus();
    area.select();
    status.textContent = 'Clipboard access failed. The prompt is selected; copy it manually. You can also download the CSV template or matching reference.';
  }
});
