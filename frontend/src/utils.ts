/** Parse Discogs title format: "Artist - Album Title" */
export function parseDiscogsTitle(title: string | null): { artist: string; album: string } {
  const [artist, ...rest] = (title ?? '').split(' - ');
  return { artist, album: rest.join(' - ') || artist };
}

/**
 * Validate that a URL points to Discogs (prevents open-redirect attacks).
 * Only allows https://discogs.com/* and https://www.discogs.com/*
 */
export function isValidDiscogsUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return (
      parsed.protocol === 'https:' &&
      (parsed.hostname === 'discogs.com' || parsed.hostname === 'www.discogs.com')
    );
  } catch {
    return false;
  }
}
