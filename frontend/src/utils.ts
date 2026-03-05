/** Parse Discogs title format: "Artist - Album Title" */
export function parseDiscogsTitle(title: string | null): { artist: string; album: string } {
  const [artist, ...rest] = (title ?? '').split(' - ');
  return { artist, album: rest.join(' - ') || artist };
}
