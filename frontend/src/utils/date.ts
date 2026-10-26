/**
 * Consistent date formatting utility: dd-mm-yyyy
 */

export function formatDate(dateStr?: string | null): string {
  if (!dateStr || dateStr.trim() === '' || dateStr === 'null') {
    return '—';
  }

  const trimmed = dateStr.trim();

  // If already in dd-mm-yyyy format (e.g. 31-03-2026)
  if (/^\d{2}-\d{2}-\d{4}$/.test(trimmed)) {
    return trimmed;
  }

  // If ISO yyyy-mm-dd (e.g. 2026-03-31)
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) {
    return `${isoMatch[3]}-${isoMatch[2]}-${isoMatch[1]}`;
  }

  // If slash format dd/mm/yyyy
  const slashMatch = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (slashMatch) {
    const d = slashMatch[1].padStart(2, '0');
    const m = slashMatch[2].padStart(2, '0');
    return `${d}-${m}-${slashMatch[3]}`;
  }

  // Parse via standard Date object
  try {
    const d = new Date(trimmed);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, '0');
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const year = d.getFullYear();
      return `${day}-${month}-${year}`;
    }
  } catch {
    // fallback
  }

  return trimmed;
}

export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr || dateStr.trim() === '' || dateStr === 'null') {
    return '—';
  }

  try {
    const d = new Date(dateStr);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, '0');
      const month = String(d.getMonth() + 1).padStart(2, '0');
      const year = d.getFullYear();
      const hours = String(d.getHours()).padStart(2, '0');
      const minutes = String(d.getMinutes()).padStart(2, '0');
      return `${day}-${month}-${year} ${hours}:${minutes}`;
    }
  } catch {
    // fallback
  }

  return formatDate(dateStr);
}
